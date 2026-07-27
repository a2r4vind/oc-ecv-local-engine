#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 27 10:58:05 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — Statistics Module (Day 11)

Computes spatial statistics (mean, min, max, std) over subsetted data,
combining Day 8's bounding-box subsetting, Day 9's temporal filtering,
and Day 10's quality-flag masking into one orchestrated query.
"""

import sys
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.netcdf_reader import open_dataset, _find_data_and_nav_groups, IngestionError
from processing.quality_mask import get_flag_definitions, build_quality_mask, QualityMaskError


class StatisticsError(Exception):
    """Raised when statistics can't be computed (bad inputs, no valid data, etc.)."""
    pass


def compute_statistics(values: np.ndarray) -> dict[str, Any]:
    """
    Generic statistics computation over any array — the core numeric
    building block, independent of how the array was produced (bbox
    subset, temporal slice, masked, or raw).
    """
    total = int(values.size)
    valid_mask = ~np.isnan(values)
    valid_count = int(np.count_nonzero(valid_mask))

    if valid_count == 0:
        return {
            "total_pixel_count": total,
            "valid_pixel_count": 0,
            "valid_fraction": 0.0,
            "mean": None,
            "min": None,
            "max": None,
            "std": None,
        }

    valid_values = values[valid_mask]
    return {
        "total_pixel_count": total,
        "valid_pixel_count": valid_count,
        "valid_fraction": round(valid_count / total, 4),
        "mean": float(np.mean(valid_values)),
        "min": float(np.min(valid_values)),
        "max": float(np.max(valid_values)),
        "std": float(np.std(valid_values)),
    }


def _compute_flat_grid_stats(
    ds: xr.Dataset,
    variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    start_date: str | None, end_date: str | None,
) -> np.ndarray:
    if variable not in ds.data_vars:
        raise StatisticsError(f"Variable '{variable}' not found in dataset")

    da = ds[variable]

    if start_date and end_date:
        if "time" not in ds.coords:
            raise StatisticsError("Dataset has no 'time' coordinate to filter on")
        da = da.sel(time=slice(np.datetime64(start_date), np.datetime64(end_date)))
        if da.sizes.get("time", 0) == 0:
            raise StatisticsError(f"No time steps fall within [{start_date}, {end_date}]")

    lat_ascending = bool(ds["lat"].values[0] < ds["lat"].values[-1])
    lon_ascending = bool(ds["lon"].values[0] < ds["lon"].values[-1])
    lat_slice = slice(lat_min, lat_max) if lat_ascending else slice(lat_max, lat_min)
    lon_slice = slice(lon_min, lon_max) if lon_ascending else slice(lon_max, lon_min)

    da = da.sel(lat=lat_slice, lon=lon_slice)

    if da.sizes.get("lat", 0) == 0 or da.sizes.get("lon", 0) == 0:
        raise StatisticsError(
            f"Bounding box [{lat_min}, {lat_max}, {lon_min}, {lon_max}] does not overlap this file"
        )

    return da.values


def _compute_swath_stats(
    data_ds: xr.Dataset,
    nav_ds: xr.Dataset,
    variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    quality_flags: list[str] | None,
) -> np.ndarray:
    if variable not in data_ds.data_vars:
        raise StatisticsError(f"Variable '{variable}' not found in dataset")

    lat_name = "latitude" if "latitude" in nav_ds.variables else "lat"
    lon_name = "longitude" if "longitude" in nav_ds.variables else "lon"
    lat_arr = nav_ds[lat_name].values
    lon_arr = nav_ds[lon_name].values

    bbox_mask = (
        (lat_arr >= lat_min) & (lat_arr <= lat_max) &
        (lon_arr >= lon_min) & (lon_arr <= lon_max)
    )

    if not bbox_mask.any():
        raise StatisticsError(
            f"Bounding box [{lat_min}, {lat_max}, {lon_min}, {lon_max}] does not overlap this granule"
        )

    line_idx, pixel_idx = np.where(bbox_mask)
    line_min, line_max = line_idx.min(), line_idx.max() + 1
    pixel_min, pixel_max = pixel_idx.min(), pixel_idx.max() + 1

    dim_names = data_ds[variable].dims
    cropped = data_ds[variable].isel({
        dim_names[0]: slice(line_min, line_max),
        dim_names[1]: slice(pixel_min, pixel_max),
    }).values
    cropped_bbox_mask = bbox_mask[line_min:line_max, pixel_min:pixel_max]

    result = np.where(cropped_bbox_mask, cropped, np.nan)

    if quality_flags:
        if "l2_flags" not in data_ds.data_vars:
            raise StatisticsError("File has no 'l2_flags' variable — cannot apply quality masking")
        flag_defs = get_flag_definitions(data_ds["l2_flags"])
        l2_flags_cropped = data_ds["l2_flags"].isel({
            dim_names[0]: slice(line_min, line_max),
            dim_names[1]: slice(pixel_min, pixel_max),
        }).values
        try:
            quality_mask_out = build_quality_mask(l2_flags_cropped, flag_defs, quality_flags)
        except QualityMaskError as e:
            raise StatisticsError(str(e)) from e
        result = np.where(quality_mask_out, np.nan, result)

    return result


def compute_regional_stats(
    file_path: str,
    variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Main entrypoint — combines bounding-box subsetting (Day 8), optional
    temporal filtering (Day 9, flat-grid files only), and optional
    quality-flag masking (Day 10, swath files only) into one query,
    then computes statistics on whatever data remains.
    """
    data_group, nav_group = _find_data_and_nav_groups(file_path)

    if data_group:
        if start_date or end_date:
            raise StatisticsError(
                "Temporal filtering is not applicable to single-granule swath "
                "files (each file already represents one short time window)"
            )
        if not nav_group:
            raise StatisticsError("Grouped/swath file has no navigation_data group")

        data_ds = open_dataset(file_path, group=data_group)
        nav_ds = open_dataset(file_path, group=nav_group)
        try:
            values = _compute_swath_stats(
                data_ds, nav_ds, variable, lat_min, lat_max, lon_min, lon_max, quality_flags
            )
        finally:
            data_ds.close()
            nav_ds.close()
    else:
        if quality_flags:
            raise StatisticsError(
                "Quality-flag masking is not applicable to flat-grid files "
                "(no l2_flags variable present)"
            )
        ds = open_dataset(file_path)
        try:
            values = _compute_flat_grid_stats(
                ds, variable, lat_min, lat_max, lon_min, lon_max, start_date, end_date
            )
        finally:
            ds.close()

    stats = compute_statistics(values)
    stats["file_name"] = Path(file_path).name
    stats["variable"] = variable
    stats["bbox"] = {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max}
    if start_date or end_date:
        stats["date_range"] = {"start": start_date, "end": end_date}
    if quality_flags:
        stats["quality_flags_masked"] = quality_flags

    return stats


if __name__ == "__main__":
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Compute regional statistics over a subsetted variable")
    parser.add_argument("file")
    parser.add_argument("variable")
    parser.add_argument("lat_min", type=float)
    parser.add_argument("lat_max", type=float)
    parser.add_argument("lon_min", type=float)
    parser.add_argument("lon_max", type=float)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--quality-flags", nargs="*")

    args = parser.parse_args()

    try:
        result = compute_regional_stats(
            args.file, args.variable, args.lat_min, args.lat_max, args.lon_min, args.lon_max,
            start_date=args.start_date, end_date=args.end_date, quality_flags=args.quality_flags,
        )
        print(json.dumps(result, indent=2, default=str))
    except (StatisticsError, IngestionError) as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)