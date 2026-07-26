#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 26 17:08:51 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — Bounding-Box Subsetting Module (Day 8)

Slices a variable to a given lat/lon bounding box. Handles both file
structures established in ingestion (Day 3-4):

  - Flat/grid files (1D lat/lon coordinates) -> direct xarray .sel() slicing.
  - Grouped/swath files (2D per-pixel lat/lon) -> boolean mask + crop to
    the smallest index-rectangle containing the region of interest, since
    swath geometry means the box isn't a clean rectangular slice in the
    underlying line/pixel index space.
"""

import sys
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.netcdf_reader import (
    open_dataset,
    _find_data_and_nav_groups,
    IngestionError,
)


class SubsettingError(Exception):
    """Raised when a bounding-box subset can't be produced (bad bbox, no overlap, etc.)."""
    pass


def _validate_bbox(lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> None:
    if lat_min >= lat_max:
        raise SubsettingError(f"lat_min ({lat_min}) must be less than lat_max ({lat_max})")
    if lon_min >= lon_max:
        raise SubsettingError(f"lon_min ({lon_min}) must be less than lon_max ({lon_max})")
    if not (-90 <= lat_min <= 90 and -90 <= lat_max <= 90):
        raise SubsettingError(f"Latitude bounds [{lat_min}, {lat_max}] outside valid [-90, 90]")
    if not (-180 <= lon_min <= 180 and -180 <= lon_max <= 180):
        raise SubsettingError(f"Longitude bounds [{lon_min}, {lon_max}] outside valid [-180, 180]")


def subset_flat_grid(
    ds: xr.Dataset, variable: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float
) -> xr.DataArray:
    """
    Slices a variable from a flat/grid dataset using xarray's coordinate
    selection. Handles both ascending and descending coordinate ordering,
    since xarray's .sel(slice(...)) requires the slice direction to match
    the coordinate's actual stored order.
    """
    if variable not in ds.data_vars:
        raise SubsettingError(f"Variable '{variable}' not found in dataset")

    lat_ascending = bool(ds["lat"].values[0] < ds["lat"].values[-1])
    lon_ascending = bool(ds["lon"].values[0] < ds["lon"].values[-1])

    lat_slice = slice(lat_min, lat_max) if lat_ascending else slice(lat_max, lat_min)
    lon_slice = slice(lon_min, lon_max) if lon_ascending else slice(lon_max, lon_min)

    subset = ds[variable].sel(lat=lat_slice, lon=lon_slice)

    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise SubsettingError(
            f"Bounding box [{lat_min}, {lat_max}, {lon_min}, {lon_max}] does not "
            f"overlap this file's spatial coverage"
        )

    return subset


def subset_swath(
    data_ds: xr.Dataset,
    nav_ds: xr.Dataset,
    variable: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> xr.DataArray:
    """
    Slices a variable from a grouped/swath dataset. Since lat/lon are 2D
    per-pixel arrays (not a regular grid), we can't do a direct coordinate
    slice. Instead:
      1. Build a boolean mask of pixels falling inside the bbox.
      2. Find the smallest index-rectangle (line/pixel range) containing
         any True pixels, and crop to that rectangle — this keeps the
         result a plain 2D array (efficient, easy to work with downstream)
         rather than a ragged/irregular selection.
      3. Mask out-of-bbox pixels *within* that cropped rectangle as NaN,
         since the rectangle itself may still include some pixels outside
         the actual bbox (swath ground tracks aren't axis-aligned).
    """
    if variable not in data_ds.data_vars:
        raise SubsettingError(f"Variable '{variable}' not found in dataset")

    lat_name = "latitude" if "latitude" in nav_ds.variables else "lat"
    lon_name = "longitude" if "longitude" in nav_ds.variables else "lon"

    lat_arr = nav_ds[lat_name].values
    lon_arr = nav_ds[lon_name].values

    mask = (
        (lat_arr >= lat_min) & (lat_arr <= lat_max) &
        (lon_arr >= lon_min) & (lon_arr <= lon_max)
    )

    if not mask.any():
        raise SubsettingError(
            f"Bounding box [{lat_min}, {lat_max}, {lon_min}, {lon_max}] does not "
            f"overlap this granule's swath coverage"
        )

    line_idx, pixel_idx = np.where(mask)
    line_min, line_max = line_idx.min(), line_idx.max() + 1
    pixel_min, pixel_max = pixel_idx.min(), pixel_idx.max() + 1

    dim_names = data_ds[variable].dims  # e.g. ("number_of_lines", "pixels_per_line")
    cropped = data_ds[variable].isel({
        dim_names[0]: slice(line_min, line_max),
        dim_names[1]: slice(pixel_min, pixel_max),
    })

    cropped_mask = mask[line_min:line_max, pixel_min:pixel_max]
    cropped_masked = cropped.where(cropped_mask)

    return cropped_masked


def subset_by_bbox(
    file_path: str, variable: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float
) -> dict[str, Any]:
    """
    Main entrypoint — detects file structure automatically and dispatches
    to the appropriate slicing function. Returns a summary dict (shape,
    actual bounds achieved, basic stats) rather than the raw array, since
    the caller (API layer) needs a JSON-serializable result; full-array
    access for visualization comes in Phase 3.
    """
    _validate_bbox(lat_min, lat_max, lon_min, lon_max)

    data_group, nav_group = _find_data_and_nav_groups(file_path)

    if data_group:
        data_ds = open_dataset(file_path, group=data_group)
        nav_ds = open_dataset(file_path, group=nav_group) if nav_group else None
        if nav_ds is None:
            data_ds.close()
            raise SubsettingError(
                "Grouped/swath file has no navigation_data group — cannot subset by lat/lon"
            )
        try:
            subset = subset_swath(data_ds, nav_ds, variable, lat_min, lat_max, lon_min, lon_max)
        finally:
            data_ds.close()
            nav_ds.close()
    else:
        ds = open_dataset(file_path)
        try:
            subset = subset_flat_grid(ds, variable, lat_min, lat_max, lon_min, lon_max)
        finally:
            ds.close()

    values = subset.values
    valid_count = int(np.count_nonzero(~np.isnan(values)))
    total_count = int(values.size)

    return {
        "variable": variable,
        "requested_bbox": {
            "lat_min": lat_min, "lat_max": lat_max,
            "lon_min": lon_min, "lon_max": lon_max,
        },
        "shape": list(subset.shape),
        "dims": list(subset.dims),
        "valid_pixel_count": valid_count,
        "total_pixel_count": total_count,
        "valid_pixel_fraction": round(valid_count / total_count, 4) if total_count else 0.0,
        "min": float(np.nanmin(values)) if valid_count > 0 else None,
        "max": float(np.nanmax(values)) if valid_count > 0 else None,
        "mean": float(np.nanmean(values)) if valid_count > 0 else None,
    }


if __name__ == "__main__":
    import json

    if len(sys.argv) != 7:
        print("Usage: python subsetting.py <file> <variable> <lat_min> <lat_max> <lon_min> <lon_max>")
        sys.exit(1)

    file_path, variable = sys.argv[1], sys.argv[2]
    lat_min, lat_max, lon_min, lon_max = (float(x) for x in sys.argv[3:7])

    try:
        result = subset_by_bbox(file_path, variable, lat_min, lat_max, lon_min, lon_max)
        print(json.dumps(result, indent=2, default=str))
    except (SubsettingError, IngestionError) as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)