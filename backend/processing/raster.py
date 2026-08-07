#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  7 04:34:10 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — Raster Encoding Module (Day 23)

Encodes subsetted pixel data for GPU-based rendering in the frontend's
deck.gl map layer, as opposed to statistics.py's scalar reduction (mean/
min/max/std). Kept as a separate module since this is a genuinely
different concern (serialization for rendering) from statistics.py's
numeric summarization, even though both consume the same subsetted array
from _get_subsetted_data().

Two encodings, chosen by the file's structure type (not a user choice):
  - Flat-grid files: 1D lat/lon on a regular grid -> PNG bitmap, rendered
    via deck.gl's BitmapLayer (a simple corner-bounds image stretch).
  - Swath files: 2D per-pixel lat/lon, non-rectilinear (real satellite
    ground-track geometry) -> packed binary point arrays, rendered via
    deck.gl's ScatterplotLayer. BitmapLayer fundamentally does not apply
    here since there's no single affine transform mapping these pixels
    onto rectangular image coordinates.

Colormaps (Viridis/Ocean/Jet) are deliberately NOT baked in here — pixel
values are sent as normalized 0-1 luminance/values, and the frontend
applies the actual color ramp as a shader lookup. This means switching
color ramps client-side never requires re-fetching data from the backend.
"""

import io
import warnings
from typing import Any

import numpy as np
from PIL import Image

from processing.statistics import _get_subsetted_data


class RasterError(Exception):
    """Raised when a raster payload can't be produced (no valid pixels, etc.)."""
    pass


MAX_RASTER_DIM = 1024  # longest side, in pixels, before block-downsampling kicks in
MAX_POINTS = 500_000   # cap on swath points sent per request, before stride-subsampling


def _downsample_2d(values: np.ndarray, max_dim: int) -> np.ndarray:
    """
    Block-averages a 2D array down to at most `max_dim` on its longest
    side, using nanmean so masked pixels don't corrupt real data into
    downsampled blocks. Relevant given Day 16's 4000x5000 stress-test
    grids — a full-resolution PNG at that size is wasteful bandwidth for
    on-screen display at typical map zoom levels.
    """
    rows, cols = values.shape
    if rows <= max_dim and cols <= max_dim:
        return values

    row_factor = max(1, int(np.ceil(rows / max_dim)))
    col_factor = max(1, int(np.ceil(cols / max_dim)))

    pad_rows = (-rows) % row_factor
    pad_cols = (-cols) % col_factor
    padded = np.pad(
        values, ((0, pad_rows), (0, pad_cols)), mode="constant", constant_values=np.nan
    )

    new_rows = padded.shape[0] // row_factor
    new_cols = padded.shape[1] // col_factor
    reshaped = padded.reshape(new_rows, row_factor, new_cols, col_factor)

    with warnings.catch_warnings():
        # nanmean on an all-NaN block (e.g. a fully-masked corner) is
        # expected and fine here — it correctly produces NaN, not a bug.
        warnings.simplefilter("ignore", category=RuntimeWarning)
        downsampled = np.nanmean(reshaped, axis=(1, 3))

    return downsampled


def encode_bitmap_png(
    values: np.ndarray, lat_coords: np.ndarray, lon_coords: np.ndarray
) -> tuple[bytes, dict[str, Any]]:
    """
    Encodes a flat-grid subsetted array as a grayscale+alpha PNG.
    Luminance = value normalized 0-255 across THIS query's own valid-data
    range (not a fixed global scale, since every query's range differs).
    Alpha = 0 for NaN/masked pixels (transparent), 255 for valid data.
    """
    if values.ndim == 3:
        # A time dimension is still present (no single-day filter was
        # applied, or multiple days matched). Day 23 renders one static
        # snapshot, not a time-animated layer — take the first time step
        # explicitly rather than silently averaging away real temporal
        # variation. Time-series animation is a natural future milestone,
        # not in scope here.
        values = values[0]

    values = _downsample_2d(values, MAX_RASTER_DIM)

    valid_mask = ~np.isnan(values)
    if not valid_mask.any():
        raise RasterError("No valid pixels in this region to render")

    value_min = float(np.min(values[valid_mask]))
    value_max = float(np.max(values[valid_mask]))
    value_range = value_max - value_min

    if value_range == 0:
        # Uniform field (all valid pixels equal) — avoid a divide-by-zero;
        # render as flat mid-gray rather than crashing on a degenerate case.
        luminance = np.where(valid_mask, 128, 0).astype(np.uint8)
    else:
        normalized = np.clip((values - value_min) / value_range, 0.0, 1.0)
        luminance = np.where(valid_mask, normalized * 255, 0).astype(np.uint8)

    alpha = np.where(valid_mask, 255, 0).astype(np.uint8)

    # Image row 0 is conventionally the TOP (north-up, standard raster
    # convention, matches deck.gl's BitmapLayer `bounds: [west, south,
    # east, north]` expectation). If lat_coords is ascending, index 0 is
    # the SOUTHERNMOST row, so it needs to end up at the BOTTOM of the
    # image, not the top — flip in that case.
    lat_ascending = bool(lat_coords[0] < lat_coords[-1])
    if lat_ascending:
        luminance = np.flipud(luminance)
        alpha = np.flipud(alpha)

    la_array = np.stack([luminance, alpha], axis=-1)  # (rows, cols, 2) -> PIL 'LA' mode
    img = Image.fromarray(la_array, mode="LA")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    meta = {
        "value_min": value_min,
        "value_max": value_max,
        "bounds": [
            float(np.min(lon_coords)),
            float(np.min(lat_coords)),
            float(np.max(lon_coords)),
            float(np.max(lat_coords)),
        ],
        "grid_shape": [int(luminance.shape[0]), int(luminance.shape[1])],
    }
    return png_bytes, meta


def encode_points_binary(
    values: np.ndarray, lat_coords: np.ndarray, lon_coords: np.ndarray
) -> tuple[bytes, dict[str, Any]]:
    """
    Encodes swath (2D per-pixel, non-rectilinear) subsetted data as a
    packed binary point payload for deck.gl's ScatterplotLayer. NaN/
    masked pixels are excluded entirely (not sent transparent) — real
    Ocean Color scenes are frequently majority cloud/land-masked (Day 8's
    finding), so sending every masked pixel as an invisible point would
    multiply payload size for no visual benefit.

    Binary layout: [uint32 point_count][float32 lon * N][float32 lat * N]
    [float32 normalized_value * N] — three separate contiguous blocks
    rather than interleaved, so the frontend can construct typed-array
    views directly at the right byte offsets without a deinterleave step.
    """
    flat_values = values.ravel()
    flat_lat = lat_coords.ravel()
    flat_lon = lon_coords.ravel()

    valid_mask = ~np.isnan(flat_values)
    if not valid_mask.any():
        raise RasterError("No valid pixels in this region to render")

    flat_values = flat_values[valid_mask]
    flat_lat = flat_lat[valid_mask]
    flat_lon = flat_lon[valid_mask]

    n_points = flat_values.size
    if n_points > MAX_POINTS:
        # Stride-based (not random) subsampling, so repeated identical
        # queries are deterministic — consistent with this project's
        # existing cache-key/reproducibility conventions elsewhere.
        stride = int(np.ceil(n_points / MAX_POINTS))
        flat_values = flat_values[::stride]
        flat_lat = flat_lat[::stride]
        flat_lon = flat_lon[::stride]
        n_points = flat_values.size

    value_min = float(np.min(flat_values))
    value_max = float(np.max(flat_values))
    value_range = value_max - value_min
    normalized = (
        np.zeros(n_points, dtype=np.float32)
        if value_range == 0
        else ((flat_values - value_min) / value_range).astype(np.float32)
    )

    header = np.array([n_points], dtype=np.uint32).tobytes()
    payload = (
        header
        + flat_lon.astype(np.float32).tobytes()
        + flat_lat.astype(np.float32).tobytes()
        + normalized.tobytes()
    )

    meta = {
        "value_min": value_min,
        "value_max": value_max,
        "point_count": n_points,
    }
    return payload, meta


def compute_regional_raster(
    file_path: str,
    variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: list[str] | None = None,
) -> tuple[bytes, str, dict[str, Any]]:
    """
    Main entrypoint for raster rendering. Reuses statistics.py's shared
    _get_subsetted_data() dispatch — the exact same structure-detection,
    subsetting, temporal-filtering, valid-range-masking, and quality-flag-
    masking pipeline /stats uses — then encodes the result for GPU
    rendering instead of reducing it to scalar statistics.

    Returns (payload_bytes, raster_type, metadata) where raster_type is
    'bitmap' (flat-grid -> BitmapLayer) or 'points' (swath ->
    ScatterplotLayer) — the two structures require different deck.gl
    layers since swath pixels aren't on a regular lat/lon grid.
    """
    subset = _get_subsetted_data(
        file_path, variable, lat_min, lat_max, lon_min, lon_max,
        start_date=start_date, end_date=end_date, quality_flags=quality_flags,
        return_coords=True,
    )
    values = subset["values"]
    structure_type = subset["structure_type"]
    lat_coords = subset["lat_coords"]
    lon_coords = subset["lon_coords"]

    if structure_type == "flat_grid":
        payload, meta = encode_bitmap_png(values, lat_coords, lon_coords)
        return payload, "bitmap", meta

    payload, meta = encode_points_binary(values, lat_coords, lon_coords)
    return payload, "points", meta