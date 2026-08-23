#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 26 18:59:08 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — Temporal Filtering Module (Day 9)

Two distinct temporal filtering needs, matching the two file structures
established in ingestion (Day 3-4):

  1. Flat/grid files with a `time` dimension (e.g. L3-style multi-day
     composites) -> slice *within* the file to a date range.
  2. Grouped/swath files (real L2 granules) -> each file represents one
     short time window, so filtering means deciding whether the *whole
     file* falls inside a requested date range — the building block for
     Day 17's multi-file batch time-series extraction.
"""

import sys
from pathlib import Path
from typing import Any, Optional, Tuple
from datetime import datetime

import numpy as np
import xarray as xr
import pandas as pd
import netCDF4 as nc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.netcdf_reader import open_dataset, extract_metadata, IngestionError


class TemporalFilterError(Exception):
    """Raised when a date range is invalid or a file has no usable time info."""
    pass


def _parse_date(date_str: str) -> datetime:
    """
    Accepts common date formats: plain dates ('2026-07-01') and full
    ISO timestamps with or without a trailing 'Z' (as NASA global attrs
    use, e.g. '2026-01-01T09:25:01.469Z').
    """
    cleaned = date_str.rstrip("Z")
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    raise TemporalFilterError(f"Could not parse date: '{date_str}'")


def _validate_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start > end:
        raise TemporalFilterError(f"start_date ({start_date}) must not be after end_date ({end_date})")
    return start, end


def filter_time_flat(
    ds: xr.Dataset, variable: str, start_date: str, end_date: str
) -> xr.DataArray:
    """
    Slices a variable's `time` dimension to a date range, for flat/grid
    files that contain multiple time steps in one file.
    """
    if "time" not in ds.coords:
        raise TemporalFilterError("Dataset has no 'time' coordinate to filter on")
    if variable not in ds.data_vars:
        raise TemporalFilterError(f"Variable '{variable}' not found in dataset")

    start, end = _validate_date_range(start_date, end_date)

    subset = ds[variable].sel(time=slice(np.datetime64(start), np.datetime64(end)))

    if subset.sizes.get("time", 0) == 0:
        raise TemporalFilterError(
            f"No time steps fall within [{start_date}, {end_date}] — "
            f"file covers {ds['time'].values.min()} to {ds['time'].values.max()}"
        )

    return subset


def granule_within_range(file_path: str, start_date: str, end_date: str) -> dict[str, Any]:
    """
    For a grouped/swath (single-granule) file: checks whether the file's
    own time coverage overlaps a requested date range at all, rather than
    slicing inside it. Returns overlap details rather than just True/False,
    since "does this file overlap the range" is more useful for batch
    filtering than a bare boolean.
    """
    start, end = _validate_date_range(start_date, end_date)

    metadata = extract_metadata(file_path)
    time_steps = metadata.get("time_steps")

    if not time_steps:
        raise TemporalFilterError(f"File '{Path(file_path).name}' has no time coverage information")

    file_start = _parse_date(time_steps[0])
    file_end = _parse_date(time_steps[-1])

    overlaps = file_start <= end and file_end >= start

    return {
        "file_name": Path(file_path).name,
        "file_time_start": time_steps[0],
        "file_time_end": time_steps[-1],
        "requested_start": start_date,
        "requested_end": end_date,
        "overlaps": overlaps,
    }

def _get_file_time_range(file_path: Path) -> Optional[Tuple[datetime, datetime, str]]:
    """
    Determine a single file's time coverage regardless of structure.
    Returns (start, end, source) or None if no usable time info exists.
    source: "time_coordinate" (flat-grid) or "global_attrs" (swath/granule).
    """
    try:
        with xr.open_dataset(file_path) as ds:
            if "time" in ds.coords or "time" in ds.dims:
                times = ds["time"].values
                if len(times) > 0:
                    start = pd.Timestamp(times.min()).to_pydatetime()
                    end = pd.Timestamp(times.max()).to_pydatetime()
                    return (start, end, "time_coordinate")
    except Exception:
        pass  # fall through to global-attribute path

    try:
        with nc.Dataset(file_path) as ds:
            start_attr = getattr(ds, "time_coverage_start", None)
            end_attr = getattr(ds, "time_coverage_end", None)
            if start_attr and end_attr:
                return (_parse_date(start_attr), _parse_date(end_attr), "global_attrs")
    except Exception:
        pass

    return None


def scan_directory_date_coverage(
    directory: str,
    extensions: Tuple[str, ...] = (".nc",),
) -> dict:
    """
    Scan every file in a directory and report aggregate valid date-range
    coverage — the "give me everything" counterpart to
    filter_files_by_date_range(), which requires explicit bounds.
    """
    directory_path = Path(directory)
    if not directory_path.is_dir():
        raise TemporalFilterError(f"Directory not found: {directory}")

    files = sorted(
        f for f in directory_path.iterdir()
        if f.is_file() and f.suffix.lower() in extensions
    )

    per_file = []
    usable_starts, usable_ends = [], []

    for f in files:
        result = _get_file_time_range(f)
        if result is None:
            per_file.append({
                "file_name": f.name,
                "has_time_info": False,
                "skip_reason": "NO_TIME_INFO",
            })
            continue

        start, end, source = result
        usable_starts.append(start)
        usable_ends.append(end)
        per_file.append({
            "file_name": f.name,
            "has_time_info": True,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "source": source,
        })

    return {
        "directory": str(directory_path),
        "total_files": len(files),
        "files_with_time_info": len(usable_starts),
        "files_without_time_info": len(files) - len(usable_starts),
        "overall_start": min(usable_starts).isoformat() if usable_starts else None,
        "overall_end": max(usable_ends).isoformat() if usable_ends else None,
        "per_file": per_file,
    }

def filter_files_by_date_range(
    directory: str, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None,
    extensions: Tuple[str, ...] = (".nc")
) -> dict[str, Any]:
    """
    Scans every .nc file in a directory and reports which ones fall
    within a requested date range — the core operation Day 17's batch
    time-series extraction will build on directly.
    
    If start_date and end_date are both omitted, delegates to
    scan_directory_date_coverage() and returns every file with usable
    time info as "matched" — the Phase D "give me everything" path.
    """
    
    if start_date is None and end_date is None:
        coverage = scan_directory_date_coverage(directory)
        matched = [
            {"file_name": pf["file_name"], "start": pf["start"],
             "end": pf["end"], "source": pf["source"]}
            for pf in coverage["per_file"] if pf["has_time_info"]
        ]
        skipped = [
            {"file_name": pf["file_name"], "reason": pf["skip_reason"]}
            for pf in coverage["per_file"] if not pf["has_time_info"]
        ]
        return {
            "requested_start": None,
            "requested_end": None,
            "total_files_scanned": coverage["total_files"],
            "matched_count": len(matched),
            "matched_files": matched,
            "skipped_count": len(skipped),
            "skipped_files": skipped,
        }

    if (start_date is None) != (end_date is None):
        raise TemporalFilterError(
            "start_date and end_date must both be provided, or both omitted for full coverage"
        )
    
    dir_path = Path(directory)
    files = sorted(dir_path.glob("*.nc"))

    if not files:
        raise TemporalFilterError(f"No .nc files found in {directory}")

    matched = []
    skipped = []

    for f in files:
        try:
            result = granule_within_range(str(f), start_date, end_date)
            if result["overlaps"]:
                matched.append(result)
        except (TemporalFilterError, IngestionError) as e:
            skipped.append({"file_name": f.name, "reason": str(e)})

    return {
        "requested_start": start_date,
        "requested_end": end_date,
        "total_files_scanned": len(files),
        "matched_count": len(matched),
        "matched_files": matched,
        "skipped_count": len(skipped),
        "skipped_files": skipped,
    }


if __name__ == "__main__":
    import json

    if len(sys.argv) == 4 and Path(sys.argv[1]).is_dir():
        # Usage: python temporal_filter.py <directory> <start_date> <end_date>
        directory, start_date, end_date = sys.argv[1], sys.argv[2], sys.argv[3]
        try:
            result = filter_files_by_date_range(directory, start_date, end_date)
            print(json.dumps(result, indent=2, default=str))
        except TemporalFilterError as e:
            print(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)

    elif len(sys.argv) == 5:
        # Usage: python temporal_filter.py <file> <variable> <start_date> <end_date>
        file_path, variable, start_date, end_date = sys.argv[1:5]
        try:
            subset = filter_time_flat(open_dataset(file_path), variable, start_date, end_date)
            print(json.dumps({
                "variable": variable,
                "shape": list(subset.shape),
                "dims": list(subset.dims),
                "time_steps_selected": [str(t) for t in subset["time"].values],
            }, indent=2, default=str))
        except (TemporalFilterError, IngestionError) as e:
            print(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)

    else:
        print(
            "Usage:\n"
            "  Single flat-grid file: python temporal_filter.py <file> <variable> <start_date> <end_date>\n"
            "  Directory of granules: python temporal_filter.py <directory> <start_date> <end_date>"
        )
        sys.exit(1)