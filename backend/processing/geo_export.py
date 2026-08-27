#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 27 13:11:24 2026

@author: akki2404
"""
"""
OC-ECV Local Engine — Georeferenced Raster Export Module (Day 38)

Exports subsetted pixel data in GIS-interoperable spatial formats,
distinct from raw_export.py's Day 37 analysis formats (CSV/.bin), which
carry values but no embedded CRS/georeferencing metadata a GIS tool can
read natively.

Two formats, chosen by file structure — NOT a user choice, unlike Day
37's CSV-vs-bin (which applies to either structure). This is a
deliberate decision, not a limitation worked around:

  - Flat-grid -> GeoTIFF. Regular 1D lat/lon grid maps directly onto
    GeoTIFF's required regular-grid model via an affine transform.
    Straightforward, standard, and lossless — no interpolation
    introduced anywhere in this path.

  - Swath -> NetCDF (CF-1.8 conventions), NOT a regridded GeoTIFF.
    Real MODIS/SWOT-style swath data has 2D per-pixel, non-rectilinear
    lat/lon (satellite ground-track geometry) — GeoTIFF has no native
    representation for this; the only way to force it into GeoTIFF
    would be resampling onto a regular grid, which invents pixel values
    between real ground-track samples. This project has consistently
    avoided introducing approximation into scientific data (Day 20's
    valid_min/max bug, Day 8/10/11's verify-before-trusting pattern),
    so swath data is exported as CF-convention NetCDF instead, exactly
    preserving native per-pixel geometry with zero interpolation.
    Verified (Day 38) via gdalinfo: GDAL's netCDF driver correctly
    recognizes this as a geolocation-array dataset (not just an opaque
    blob), confirming real GIS tools can georeference it without needing
    a companion regridding step.

Reuses statistics.py's _get_subsetted_data() exactly as raster.py and
raw_export.py do — same structure-detection, subsetting, temporal-
filtering, and quality-flag-masking pipeline, just a different
serialization at the end.
"""

import io
import tempfile
import os

import numpy as np
import rasterio
from rasterio.transform import from_bounds
import xarray as xr

from processing.statistics import _get_subsetted_data


class GeoExportError(Exception):
    """Raised when a georeferenced export payload can't be produced (no valid pixels, etc.)."""
    pass


def _collapse_time_dim(values: np.ndarray) -> np.ndarray:
    """
    Same convention as raster.py's encode_bitmap_png() and raw_export.py's
    _collapse_time_dim(): if a time dimension survived subsetting, take
    the first time step explicitly — GeoTIFF/single-slice-NetCDF export
    can't represent a 3D array cleanly, and silently averaging across
    time would be a scientific-correctness compromise this project
    hasn't made anywhere else.
    """
    if values.ndim == 3:
        return values[0]
    return values


def encode_geotiff(
    values: np.ndarray, lat_coords: np.ndarray, lon_coords: np.ndarray, variable: str,
) -> bytes:
    """
    Encodes flat-grid subsetted data as a single-band, float32 GeoTIFF,
    CRS EPSG:4326 (WGS84 lat/lon — correct for every ECV product ingested
    by this project so far; none have used a projected CRS), NaN as
    nodata.

    rasterio has no clean in-memory write API for GTiff (unlike read,
    which supports MemoryFile well) in the version pinned here, so this
    writes to a real temp file and reads the bytes back — verified
    working in both source and the compiled PyInstaller sidecar (Day 38
    diagnostics check) before this function was written.
    """
    values = _collapse_time_dim(values)

    valid_mask = ~np.isnan(values)
    if not valid_mask.any():
        raise GeoExportError("No valid pixels in this region to export")

    lat_min, lat_max = float(np.min(lat_coords)), float(np.max(lat_coords))
    lon_min, lon_max = float(np.min(lon_coords)), float(np.max(lon_coords))
    n_rows, n_cols = values.shape

    # North-up: row 0 must be northernmost, matching raster.py's and
    # raw_export.py's established orientation convention across this
    # project's exports.
    lat_ascending = bool(lat_coords[0] < lat_coords[-1])
    export_values = np.flipud(values) if lat_ascending else values

    transform = from_bounds(lon_min, lat_min, lon_max, lat_max, width=n_cols, height=n_rows)

    fd, tmp_path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    try:
        with rasterio.open(
            tmp_path, "w",
            driver="GTiff",
            height=n_rows, width=n_cols, count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
            nodata=np.nan,
        ) as dst:
            dst.write(export_values.astype(np.float32), 1)
            dst.update_tags(1, VARIABLE=variable)

        with open(tmp_path, "rb") as f:
            payload = f.read()
    finally:
        os.remove(tmp_path)

    return payload


def encode_netcdf_swath(
    values: np.ndarray, lat_coords: np.ndarray, lon_coords: np.ndarray, variable: str,
) -> bytes:
    """
    Encodes swath subsetted data as CF-1.8 NetCDF, preserving native 2D
    per-pixel lat/lon exactly as returned by _get_subsetted_data() — no
    regridding, no interpolation. Mirrors the CF grid-mapping convention
    verified (Day 38) against gdalinfo output: a dummy 'crs' variable
    with grid_mapping_name=latitude_longitude, referenced by the data
    variable's own grid_mapping attribute, plus a top-level Conventions
    attribute so GDAL/QGIS/cf-xarray-aware tools recognize the structure.

    Same in-memory-write limitation as encode_geotiff() — xarray's
    to_netcdf() writes to a real path, not a return-bytes API — so this
    uses a temp file and reads the bytes back.
    """
    values = _collapse_time_dim(values)

    valid_mask = ~np.isnan(values)
    if not valid_mask.any():
        raise GeoExportError("No valid pixels in this region to export")

    ds = xr.Dataset(
        data_vars={
            variable: (
                ("y", "x"),
                values.astype(np.float32),
                {
                    "coordinates": "lat lon",
                    "grid_mapping": "crs",
                    "_FillValue": np.float32(np.nan),
                },
            ),
        },
        coords={
            "lat": (
                ("y", "x"),
                lat_coords.astype(np.float64),
                {"units": "degrees_north", "standard_name": "latitude"},
            ),
            "lon": (
                ("y", "x"),
                lon_coords.astype(np.float64),
                {"units": "degrees_east", "standard_name": "longitude"},
            ),
        },
    )
    ds["crs"] = xr.DataArray(
        0,
        attrs={
            "grid_mapping_name": "latitude_longitude",
            "longitude_of_prime_meridian": 0.0,
            "semi_major_axis": 6378137.0,
            "inverse_flattening": 298.257223563,
        },
    )
    ds.attrs["Conventions"] = "CF-1.8"
    ds.attrs["title"] = f"OC-ECV Local Engine swath export — {variable}"

    fd, tmp_path = tempfile.mkstemp(suffix=".nc")
    os.close(fd)
    try:
        ds.to_netcdf(tmp_path)
        with open(tmp_path, "rb") as f:
            payload = f.read()
    finally:
        os.remove(tmp_path)

    return payload


def compute_geo_export(
    file_path: str,
    variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: list[str] | None = None,
) -> tuple[bytes, str, str]:
    """
    Main entrypoint for georeferenced export. Reuses the same
    _get_subsetted_data() dispatch as compute_regional_raster() (Day 23)
    and compute_raw_export() (Day 37). Format is NOT a caller choice
    (unlike Day 37's csv/bin) — it's determined by file structure, since
    that's the whole point of this module: pick the format that can
    actually represent each structure's real geometry without inventing
    data.

    Returns (payload_bytes, media_type, export_kind) where export_kind
    is 'geotiff' or 'netcdf_swath' — passed back to the endpoint so it
    can set the right filename/Content-Disposition without re-deriving
    structure_type itself.
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
        payload = encode_geotiff(values, lat_coords, lon_coords, variable)
        return payload, "image/tiff", "geotiff"

    payload = encode_netcdf_swath(values, lat_coords, lon_coords, variable)
    return payload, "application/x-netcdf", "netcdf_swath"