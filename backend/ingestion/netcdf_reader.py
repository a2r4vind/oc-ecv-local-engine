"""
OC-ECV Local Engine — NetCDF/HDF Ingestion Module (Day 3, updated)

Parses Ocean Color ECV files using xarray/netCDF4. Handles two structural
cases, since real NASA OB.DAAC L2 swath files and simpler L3-style grid
files are organized differently:

  1. Flat/grid files (e.g. L3, or our synthetic test fixture) — variables
     and 1D lat/lon coordinates live at the dataset root.
  2. Grouped/swath files (real NASA L2 products) — variables live inside
     a `geophysical_data` group, and lat/lon live inside a `navigation_data`
     group as full 2D per-pixel swath arrays, not a 1D coordinate grid.
"""

from pathlib import Path
from typing import Any
import netCDF4
import xarray as xr
import numpy as np


KNOWN_ECV_PREFIXES = {
    "chlorophyll": ["chlor_a", "chl_ocx", "chl_a"],
    "reflectance": ["Rrs_", "Rrs"],
}

# Standard OB.DAAC L2 group names where science data actually lives.
DATA_GROUP_CANDIDATES = ["geophysical_data"]
NAV_GROUP_CANDIDATES = ["navigation_data"]


class IngestionError(Exception):
    """Raised when a file can't be opened or fails structural validation."""
    pass


def list_groups(file_path: str) -> list[str]:
    """Returns the names of all top-level netCDF4 groups in the file."""
    with netCDF4.Dataset(file_path, "r") as nc:
        return list(nc.groups.keys())


def open_dataset(file_path: str, group: str | None = None) -> xr.Dataset:
    """
    Opens a NetCDF/HDF file (optionally a specific group) via xarray.
    Raises IngestionError with a clear message on failure.
    """
    path = Path(file_path)
    if not path.exists():
        raise IngestionError(f"File not found: {file_path}")

    try:
        ds = xr.open_dataset(path, engine="netcdf4", decode_times=True, group=group)
    except Exception as e:
        group_label = f" (group='{group}')" if group else ""
        raise IngestionError(f"Failed to open '{path.name}'{group_label}: {e}") from e

    return ds


def _find_data_and_nav_groups(file_path: str) -> tuple[str | None, str | None]:
    """Detects which groups (if any) hold science data and lat/lon."""
    groups = list_groups(file_path)
    data_group = next((g for g in DATA_GROUP_CANDIDATES if g in groups), None)
    nav_group = next((g for g in NAV_GROUP_CANDIDATES if g in groups), None)
    return data_group, nav_group


def extract_metadata(file_path: str) -> dict[str, Any]:
    """
    Extracts dimensions, variables, spatial bounds, and time steps —
    handling both flat/grid files and grouped/swath files transparently.
    """
    data_group, nav_group = _find_data_and_nav_groups(file_path)

    # Root dataset — always has global attrs; may or may not have
    # variables/coords depending on whether this file uses groups.
    root_ds = open_dataset(file_path)

    metadata: dict[str, Any] = {
        "structure": "grouped_swath" if data_group else "flat_grid",
        "global_attrs": dict(root_ds.attrs),
    }

    # --- Case 1: variables live in a nested geophysical_data group ---
    if data_group:
        data_ds = open_dataset(file_path, group=data_group)
        metadata["dimensions"] = {name: size for name, size in data_ds.sizes.items()}
        metadata["variables"] = list(data_ds.data_vars.keys())
        metadata["coordinates"] = list(data_ds.coords.keys())
        data_ds.close()
    else:
        metadata["dimensions"] = {name: size for name, size in root_ds.sizes.items()}
        metadata["variables"] = list(root_ds.data_vars.keys())
        metadata["coordinates"] = list(root_ds.coords.keys())

    # --- Spatial bounds ---
    # Grouped swath files: lat/lon are 2D per-pixel arrays inside navigation_data.
    if nav_group:
        nav_ds = open_dataset(file_path, group=nav_group)
        for lat_name in ("latitude", "lat"):
            if lat_name in nav_ds.variables:
                lat_vals = nav_ds[lat_name].values
                metadata["lat_range"] = [float(np.nanmin(lat_vals)), float(np.nanmax(lat_vals))]
                break
        for lon_name in ("longitude", "lon"):
            if lon_name in nav_ds.variables:
                lon_vals = nav_ds[lon_name].values
                metadata["lon_range"] = [float(np.nanmin(lon_vals)), float(np.nanmax(lon_vals))]
                break
        nav_ds.close()
    else:
        # Flat/grid files: 1D lat/lon coordinates at the root.
        for lat_name in ("lat", "latitude"):
            if lat_name in root_ds.coords:
                lat_vals = root_ds.coords[lat_name].values
                metadata["lat_range"] = [float(lat_vals.min()), float(lat_vals.max())]
                break
        for lon_name in ("lon", "longitude"):
            if lon_name in root_ds.coords:
                lon_vals = root_ds.coords[lon_name].values
                metadata["lon_range"] = [float(lon_vals.min()), float(lon_vals.max())]
                break

    # Fallback: NASA L2 files also carry pre-computed geospatial bounds as
    # global attributes — use these if group-based extraction above found nothing.
    if "lat_range" not in metadata and "geospatial_lat_min" in root_ds.attrs:
        metadata["lat_range"] = [
            float(root_ds.attrs["geospatial_lat_min"]),
            float(root_ds.attrs["geospatial_lat_max"]),
        ]
    if "lon_range" not in metadata and "geospatial_lon_min" in root_ds.attrs:
        metadata["lon_range"] = [
            float(root_ds.attrs["geospatial_lon_min"]),
            float(root_ds.attrs["geospatial_lon_max"]),
        ]

    # --- Time ---
    if "time_coverage_start" in root_ds.attrs:
        metadata["time_steps"] = [
            root_ds.attrs.get("time_coverage_start"),
            root_ds.attrs.get("time_coverage_end"),
        ]
        metadata["num_time_steps"] = 1  # single swath granule = one time window
    elif "time" in root_ds.coords:
        time_vals = root_ds.coords["time"].values
        metadata["time_steps"] = [str(t) for t in time_vals]
        metadata["num_time_steps"] = len(time_vals)

    root_ds.close()
    return metadata


def identify_ecv_variables(file_path: str) -> dict[str, list[str]]:
    """
    Scans the dataset's variables (searching the geophysical_data group
    first if present, falling back to root) and buckets them by known
    Ocean Color ECV category.
    """
    data_group, _ = _find_data_and_nav_groups(file_path)
    ds = open_dataset(file_path, group=data_group) if data_group else open_dataset(file_path)

    found: dict[str, list[str]] = {category: [] for category in KNOWN_ECV_PREFIXES}
    for var_name in ds.data_vars:
        for category, prefixes in KNOWN_ECV_PREFIXES.items():
            if any(var_name.startswith(p) or var_name == p for p in prefixes):
                found[category].append(var_name)

    ds.close()
    return found


def validate_structure(file_path: str) -> dict[str, Any]:
    """
    Basic structural validation — checks spatial bounds are sane and at
    least one recognized ECV variable is present.
    """
    issues: list[str] = []
    metadata = extract_metadata(file_path)

    if "lat_range" in metadata:
        lat_min, lat_max = metadata["lat_range"]
        if not (-90 <= lat_min <= 90 and -90 <= lat_max <= 90):
            issues.append(f"Latitude range {metadata['lat_range']} outside valid [-90, 90]")
    else:
        issues.append("Could not determine latitude range from file")

    if "lon_range" in metadata:
        lon_min, lon_max = metadata["lon_range"]
        if not (-180 <= lon_min <= 180 and -180 <= lon_max <= 180):
            issues.append(f"Longitude range {metadata['lon_range']} outside valid [-180, 180]")
    else:
        issues.append("Could not determine longitude range from file")

    ecv_vars = identify_ecv_variables(file_path)
    if not any(ecv_vars.values()):
        issues.append("No recognized Ocean Color ECV variables found in this file")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "ecv_variables_found": ecv_vars,
    }


def parse_file(file_path: str) -> dict[str, Any]:
    """
    Main entrypoint — opens a file (detecting flat vs. grouped structure
    automatically) and returns a full ingestion summary: metadata, ECV
    variable classification, and validation results.
    """
    path = Path(file_path)
    if not path.exists():
        raise IngestionError(f"File not found: {file_path}")

    result = {
        "file_name": path.name,
        "metadata": extract_metadata(file_path),
        "ecv_variables": identify_ecv_variables(file_path),
        "validation": validate_structure(file_path),
    }
    return result


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) != 2:
        print("Usage: python netcdf_reader.py <path-to-netcdf-file>")
        sys.exit(1)

    result = parse_file(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))