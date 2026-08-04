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
import threading
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.netcdf_reader import open_dataset, _find_data_and_nav_groups, IngestionError
from processing.quality_mask import get_flag_definitions, build_quality_mask, QualityMaskError
from processing.parallel_utils import run_parallel
from processing.temporal_filter import filter_files_by_date_range, TemporalFilterError
from caching.query_cache import get_cached_result, store_result

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

def _apply_valid_range_mask(da: xr.DataArray, values: np.ndarray) -> np.ndarray:
    """
    xarray's decode_cf only honors _FillValue/missing_value, NOT valid_min/
    valid_max — unlike netCDF4's own auto-masking, which excludes both.
    This gap let physically-invalid values (e.g. SST of -72.75°C, outside
    this file's own stated valid range) silently pass through as if they
    were real decoded data. Reconstructs the valid range in scaled units
    using the variable's own attrs/encoding (read dynamically, not
    hardcoded, consistent with this project's Day 10 flag-handling
    convention) and masks anything outside it as NaN.
    """
    attrs = da.attrs
    if "valid_min" not in attrs and "valid_max" not in attrs:
        return values  # nothing to do — file doesn't define a valid range

    scale = da.encoding.get("scale_factor", 1.0)
    offset = da.encoding.get("add_offset", 0.0)

    valid_min = attrs.get("valid_min")
    valid_max = attrs.get("valid_max")
    scaled_min = valid_min * scale + offset if valid_min is not None else -np.inf
    scaled_max = valid_max * scale + offset if valid_max is not None else np.inf

    out_of_range = (values < scaled_min) | (values > scaled_max)
    if out_of_range.any():
        values = np.where(out_of_range, np.nan, values)
    return values

def _normalize_lon_to_file_convention(lon_coord: np.ndarray, lon_min: float, lon_max: float) -> tuple[float, float]:
    """
    Some products (e.g. RSS SMAP SSS) encode longitude as 0-360 instead of
    the -180/180 convention used everywhere else in this pipeline (synthetic
    fixtures, all NASA OB.DAAC L2 files tested so far). Detects this from
    the file's own lon coordinate range and converts the user-facing
    -180/180 bbox query into the file's native convention on the fly, so
    callers never need to know or care which convention a given file uses.

    Does not handle bboxes that cross the antimeridian in the converted
    space (e.g. spanning 350-10 after conversion) — flagged as a known
    limitation, not silently mishandled: raises clearly rather than
    returning a wrong/empty result.
    """
    file_is_0_360 = bool(lon_coord.min() >= 0) and bool(lon_coord.max() > 180)
    if not file_is_0_360:
        return lon_min, lon_max  # file already uses -180/180, no conversion needed

    def to_0_360(x: float) -> float:
        return x + 360 if x < 0 else x

    new_min, new_max = to_0_360(lon_min), to_0_360(lon_max)
    if new_min > new_max:
        raise StatisticsError(
            f"Bounding box [{lon_min}, {lon_max}] crosses the antimeridian in this "
            f"file's 0-360 longitude convention — not currently supported"
        )
    return new_min, new_max

def _get_lat_lon_names(ds: xr.Dataset) -> tuple[str, str]:
    """
    Some products (e.g. real CCMP OSVW, SWOT SSH) use full 'latitude'/
    'longitude' names instead of the 'lat'/'lon' convention used everywhere
    else in this pipeline (synthetic fixtures, MODIS OB.DAAC files, SMAP
    SSS). Checks ds.variables (covers both coords and data_vars) so this
    works regardless of whether lat/lon are registered as dimension
    coordinates or plain variables.
    """
    lat_name = "lat" if "lat" in ds.variables else ("latitude" if "latitude" in ds.variables else None)
    lon_name = "lon" if "lon" in ds.variables else ("longitude" if "longitude" in ds.variables else None)
    if lat_name is None or lon_name is None:
        raise StatisticsError("Could not find lat/lon coordinates (checked 'lat'/'lon' and 'latitude'/'longitude')")
    return lat_name, lon_name

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
            
    lat_name, lon_name = _get_lat_lon_names(ds)

    # normalize longitude as per file convention
    lon_min, lon_max = _normalize_lon_to_file_convention(ds[lon_name].values, lon_min, lon_max)

    lat_ascending = bool(ds[lat_name].values[0] < ds[lat_name].values[-1])
    lon_ascending = bool(ds[lon_name].values[0] < ds[lon_name].values[-1])
    lat_slice = slice(lat_min, lat_max) if lat_ascending else slice(lat_max, lat_min)
    lon_slice = slice(lon_min, lon_max) if lon_ascending else slice(lon_max, lon_min)

    da = da.sel({lat_name: lat_slice, lon_name: lon_slice})

    if da.sizes.get(lat_name, 0) == 0 or da.sizes.get(lon_name, 0) == 0:
        raise StatisticsError(
            f"Bounding box [{lat_min}, {lat_max}, {lon_min}, {lon_max}] does not overlap this file"
        )

    return _apply_valid_range_mask(da, da.values)
            

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
    cropped_da = data_ds[variable].isel({
        dim_names[0]: slice(line_min, line_max),
        dim_names[1]: slice(pixel_min, pixel_max),
    })
    cropped = _apply_valid_range_mask(cropped_da, cropped_da.values)
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
        ds = open_dataset(file_path)
        try:
            lat_name, _ = _get_lat_lon_names(ds)
            is_swath_shaped = ds[lat_name].ndim == 2
        except StatisticsError:
            is_swath_shaped = False

        if is_swath_shaped:
            # Groupless swath case (e.g. SWOT SSH): no geophysical_data/
            # navigation_data grouping convention, but lat/lon are still
            # 2D per-pixel arrays like real MODIS L2 swaths. Reuse
            # _compute_swath_stats directly against the same flat dataset
            # for both "data" and "nav" roles, rather than building new
            # logic — the function already handles latitude/lat naming.
            if start_date or end_date:
                raise StatisticsError(
                    "Temporal filtering is not applicable to single-granule "
                    "swath-shaped files"
                )
            try:
                values = _compute_swath_stats(
                    ds, ds, variable, lat_min, lat_max, lon_min, lon_max, quality_flags
                )
            finally:
                ds.close()
        else:
            if quality_flags:
                raise StatisticsError(
                    "Quality-flag masking is not applicable to flat-grid files "
                    "(no l2_flags variable present)"
                )
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

_netcdf_file_lock = threading.Lock()

def compute_regional_stats_multivar(
    path: str,
    variables: list[str],
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: list[str] | None = None,
    max_workers: int | None = None,
) -> dict:
    """
    Runs compute_regional_stats() across multiple variables concurrently.
    IMPORTANT: this conda-forge netCDF4/HDF5 build is NOT thread-safe for
    concurrent reads of the same physical file — verified empirically on
    Day 16 (repeated trials produced intermittent 'NetCDF: HDF error',
    'Not a valid ID', and 'Can't open HDF5 attribute' failures under real
    concurrency). A module-level lock serializes the entire open-through-
    compute call per variable, eliminating the race. Profiling showed
    threading gives no meaningful speedup here anyway (I/O-bound, ~1.1x
    at best), so this trades away no real performance.
    """

    def _one(var):
        with _netcdf_file_lock:
            return compute_regional_stats(
                path, var, lat_min, lat_max, lon_min, lon_max,
                start_date=start_date, end_date=end_date, quality_flags=quality_flags,
            )

    raw_results = run_parallel(_one, variables, max_workers=max_workers)

    output = {}
    for var, result, error in raw_results:
        if error is not None:
            output[var] = {"error": str(error)}
        else:
            output[var] = result
    return output

def compute_batch_timeseries(
    directory: str,
    variable: str,
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: list[str] | None = None,
    max_workers: int | None = None,
    serialize_file_access: bool = True,
) -> dict:
    """Computes regional stats across every file in `directory` that falls
    within [start_date, end_date] (via Day 9's filter_files_by_date_range),
    building a time-series. Each file is independent — unlike Day 16's
    multi-variable-same-file case, there's no shared file handle here, but
    HDF5's thread-safety is a global library concern, not guaranteed to be
    strictly per-file-scoped. `serialize_file_access` defaults to True as a
    safe starting point; Day 17's empirical A/B test determines whether it
    can be safely set to False for a real speedup."""

        
    try:
        scan_result = filter_files_by_date_range(directory, start_date, end_date)
    except TemporalFilterError as e:
        raise StatisticsError(str(e)) from e

    matched_paths = [
        str(Path(directory) / m["file_name"]) for m in scan_result["matched_files"]
    ]
    if not matched_paths:
        raise StatisticsError(f"No files in '{directory}' fall within [{start_date}, {end_date}]")

    lock = _netcdf_file_lock if serialize_file_access else None

    def _one(file_path):
        if lock:
            with lock:
                return compute_regional_stats(
                    file_path, variable, lat_min, lat_max, lon_min, lon_max,
                    quality_flags=quality_flags,
                )
        return compute_regional_stats(
            file_path, variable, lat_min, lat_max, lon_min, lon_max,
            quality_flags=quality_flags,
        )

    raw_results = run_parallel(_one, matched_paths, max_workers=max_workers)

    timeseries = []
    for file_path, result, error in raw_results:
        entry = {"file": Path(file_path).name}
        if error is not None:
            if "does not overlap" in str(error):
                entry["skipped"] = True
                entry["reason"] = str(error)
            else:
                entry["error"] = str(error)
        else:
            entry.update(result)
        timeseries.append(entry)

    timeseries.sort(key=lambda e: e["file"])
    return {"variable": variable, "file_count": len(timeseries), "timeseries": timeseries}


def compute_regional_stats_cached(
    file_path: str, variable: str,
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    start_date: str | None = None, end_date: str | None = None,
    quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    """Cache-aware wrapper around compute_regional_stats(). Checks SQLite
    cache first (keyed on all params + file mtime); on miss, computes and
    stores the result. Callers who need to force recomputation should call
    compute_regional_stats() directly instead."""
    cached = get_cached_result(
        file_path, variable, lat_min, lat_max, lon_min, lon_max,
        start_date, end_date, quality_flags,
    )
    if cached is not None:
        cached["_cache_hit"] = True
        return cached

    result = compute_regional_stats(
        file_path, variable, lat_min, lat_max, lon_min, lon_max,
        start_date=start_date, end_date=end_date, quality_flags=quality_flags,
    )
    store_result(
        file_path, variable, lat_min, lat_max, lon_min, lon_max, result,
        start_date=start_date, end_date=end_date, quality_flags=quality_flags,
    )
    result["_cache_hit"] = False
    return result

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