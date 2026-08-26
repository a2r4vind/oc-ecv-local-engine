#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OC-ECV Local Engine — Raw Data Matrix Export Module (Day 37)

Exports subsetted pixel data in analysis-ready formats (CSV, packed
binary) at full physical-unit precision — distinct from raster.py's
Day 23 encodings, which are purpose-built for GPU rendering:
  - encode_bitmap_png() normalizes values to 0-255 luminance for display.
  - encode_points_binary() normalizes values to 0-1 for colormap lookup.
Both are lossy for downstream numeric analysis (GIS, spreadsheets,
external Python scripts) — this module sends the actual subsetted
values as-is (minus quality/NaN masking already applied upstream by
_get_subsetted_data()), so this is the "ground truth" export path.

Reuses statistics.py's _get_subsetted_data() exactly as raster.py's
compute_regional_raster() does — same structure-detection, subsetting,
temporal-filtering, and quality-flag-masking pipeline, just a different
serialization at the end.

Two formats, both applying to either structure type (flat-grid or
swath), chosen by the caller (a genuine user choice here, unlike
raster.py's PNG-vs-points branch, which is dictated by file structure):

  - CSV: long format (lat, lon, value per row) for both structures.
    A "grid matrix" CSV (rows=lat, cols=lon) was considered and
    rejected — it only makes sense for flat-grid; swath's non-
    rectilinear per-pixel lat/lon has no natural row/column mapping
    onto a 2D CSV grid. Long format generalizes cleanly to both, at
    the cost of repeating lat/lon per row (acceptable — CSV is not a
    bandwidth-sensitive path the way /raster's binary payload is).
    NaN/masked pixels are excluded entirely, consistent with Day 23's
    encode_points_binary() swath convention.

  - .bin: raw (unnormalized) values, in physical units.
    Flat-grid layout: [uint32 n_rows][uint32 n_cols][float64 lat_min]
    [float64 lat_max][float64 lon_min][float64 lon_max]
    [float32 values...] row-major, NaN preserved (grid position
    matters for a regular grid, unlike swath's point cloud — dropping
    a masked cell would silently shift every subsequent cell in the
    row). Row 0 = northernmost row (max lat), matching
    encode_bitmap_png()'s north-up convention, so raster.py's and this
    module's binary outputs agree on orientation.
    Swath layout: [uint32 count][float32 lon×N][float32 lat×N]
    [float32 raw_value×N] — same triplet-of-contiguous-blocks layout as
    encode_points_binary(), but values are NOT normalized, and there is
    no MAX_POINTS stride-subsampling — this is an analysis export, not
    a render payload, so completeness matters more than payload size.
"""

import io
# from typing import Any

import numpy as np

from processing.statistics import _get_subsetted_data


class RawExportError(Exception):
    """Raised when a raw export payload can't be produced (no valid pixels, etc.)."""
    pass


def _collapse_time_dim(values: np.ndarray) -> np.ndarray:
    """
    Same convention as raster.py's encode_bitmap_png(): if a time
    dimension survived subsetting (no single-day filter applied, or
    multiple days matched), take the first time step explicitly rather
    than silently averaging or exporting a 3D array a CSV/flat-binary
    format can't represent cleanly.
    """
    if values.ndim == 3:
        return values[0]
    return values


def encode_csv_long(
    values: np.ndarray, lat_coords: np.ndarray, lon_coords: np.ndarray, structure_type: str,
) -> bytes:
    """
    Encodes subsetted data as a long-format CSV: one row per valid pixel,
    `lat,lon,value` columns. Works identically for flat-grid (lat_coords/
    lon_coords are 1D, broadcast via meshgrid) and swath (lat_coords/
    lon_coords are already 2D, same shape as values) inputs.

    Uses np.savetxt over a StringIO rather than the csv module's
    row-by-row writer — Day 16's stress-test grids ran into the
    millions of pixels, and a Python-level per-row loop at that scale
    is a real, avoidable bottleneck for a synchronous request/response
    endpoint.
    """
    values = _collapse_time_dim(values)

    if structure_type == "flat_grid":
        # lat_coords/lon_coords are 1D axis coordinates on a regular
        # grid — broadcast to per-pixel 2D arrays matching values' shape.
        lon_grid, lat_grid = np.meshgrid(lon_coords, lat_coords)
    else:
        # Swath: lat_coords/lon_coords are already 2D, one per pixel.
        lat_grid = lat_coords
        lon_grid = lon_coords

    flat_values = values.ravel()
    flat_lat = lat_grid.ravel()
    flat_lon = lon_grid.ravel()

    valid_mask = ~np.isnan(flat_values)
    if not valid_mask.any():
        raise RawExportError("No valid pixels in this region to export")

    flat_values = flat_values[valid_mask]
    flat_lat = flat_lat[valid_mask]
    flat_lon = flat_lon[valid_mask]

    buf = io.StringIO()
    buf.write("lat,lon,value\n")
    data = np.column_stack([flat_lat, flat_lon, flat_values])
    np.savetxt(buf, data, delimiter=",", fmt="%.6f")

    return buf.getvalue().encode("utf-8")


def encode_bin_flat_grid(
    values: np.ndarray, lat_coords: np.ndarray, lon_coords: np.ndarray,
) -> bytes:
    """
    Packs a flat-grid subsetted array as raw (unnormalized) float32
    values, NaN preserved, row-major, north-up (row 0 = max lat) —
    matching encode_bitmap_png()'s orientation convention so both
    raster.py's and this module's binary outputs agree on row order.

    Layout: [uint32 n_rows][uint32 n_cols][float64 lat_min]
    [float64 lat_max][float64 lon_min][float64 lon_max]
    [float32 values...]
    """
    values = _collapse_time_dim(values)

    valid_mask = ~np.isnan(values)
    if not valid_mask.any():
        raise RawExportError("No valid pixels in this region to export")

    # North-up: if lat_coords is ascending, row 0 of the coordinate array
    # is the southernmost row — flip so row 0 ends up northernmost, the
    # exact same check/flip encode_bitmap_png() applies.
    lat_ascending = bool(lat_coords[0] < lat_coords[-1])
    export_values = np.flipud(values) if lat_ascending else values

    n_rows, n_cols = export_values.shape
    header = np.array([n_rows, n_cols], dtype=np.uint32).tobytes()
    bounds = np.array(
        [
            float(np.min(lat_coords)), float(np.max(lat_coords)),
            float(np.min(lon_coords)), float(np.max(lon_coords)),
        ],
        dtype=np.float64,
    ).tobytes()
    body = export_values.astype(np.float32).tobytes()

    return header + bounds + body


def encode_bin_swath(
    values: np.ndarray, lat_coords: np.ndarray, lon_coords: np.ndarray,
) -> bytes:
    """
    Packs swath subsetted data as raw (unnormalized) float32 point
    triplets. Same contiguous-block layout as raster.py's
    encode_points_binary() (lon block, then lat block, then value block
    — not interleaved, so the frontend can construct typed-array views
    directly), but values are NOT normalized to 0-1, and there is no
    MAX_POINTS stride-subsampling — this is an analysis export, not a
    render payload, so completeness matters more than payload size here.

    Layout: [uint32 count][float32 lon×N][float32 lat×N]
    [float32 raw_value×N]
    """
    values = _collapse_time_dim(values)

    flat_values = values.ravel()
    flat_lat = lat_coords.ravel()
    flat_lon = lon_coords.ravel()

    valid_mask = ~np.isnan(flat_values)
    if not valid_mask.any():
        raise RawExportError("No valid pixels in this region to export")

    flat_values = flat_values[valid_mask]
    flat_lat = flat_lat[valid_mask]
    flat_lon = flat_lon[valid_mask]

    n_points = flat_values.size
    header = np.array([n_points], dtype=np.uint32).tobytes()
    payload = (
        header
        + flat_lon.astype(np.float32).tobytes()
        + flat_lat.astype(np.float32).tobytes()
        + flat_values.astype(np.float32).tobytes()
    )
    return payload


def compute_raw_export(
    file_path: str,
    variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    export_format: str,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: list[str] | None = None,
) -> tuple[bytes, str]:
    """
    Main entrypoint for raw data export. Reuses the same
    _get_subsetted_data() dispatch as compute_regional_raster() (Day 23)
    and compute_regional_stats() — same structure-detection, subsetting,
    temporal-filtering, and quality-flag-masking pipeline — then
    serializes the result as CSV or packed binary instead of a
    rendering payload or scalar statistics.

    `export_format` is 'csv' or 'bin' (validated here, not left to the
    caller, so an invalid value fails before any subsetting work is done).

    Returns (payload_bytes, media_type).
    """
    if export_format not in ("csv", "bin"):
        raise RawExportError(f"Unsupported export format: {export_format!r}")

    subset = _get_subsetted_data(
        file_path, variable, lat_min, lat_max, lon_min, lon_max,
        start_date=start_date, end_date=end_date, quality_flags=quality_flags,
        return_coords=True,
    )
    values = subset["values"]
    structure_type = subset["structure_type"]
    lat_coords = subset["lat_coords"]
    lon_coords = subset["lon_coords"]

    if export_format == "csv":
        payload = encode_csv_long(values, lat_coords, lon_coords, structure_type)
        return payload, "text/csv"

    if structure_type == "flat_grid":
        payload = encode_bin_flat_grid(values, lat_coords, lon_coords)
    else:
        payload = encode_bin_swath(values, lat_coords, lon_coords)
    return payload, "application/octet-stream"