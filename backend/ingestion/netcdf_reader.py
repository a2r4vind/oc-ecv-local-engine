"""
OC-ECV Local Engine — NetCDF/HDF Ingestion Module (Day 3-4)

Parses Ocean Color ECV files using xarray/netCDF4. Handles both flat/grid
files (L3-style, or our synthetic test fixture) and grouped/swath files
(real NASA L2 products with geophysical_data/navigation_data groups).

Validation logic lives in backend/validation/file_validator.py — this
module's job is purely "read the file and describe its structure";
"is this structure actually usable" is the validator's job.
"""

from pathlib import Path
from typing import Any
import netCDF4
import xarray as xr
import numpy as np
import sys

# Ensure backend/ is on sys.path so `validation` resolves as a sibling
# package, regardless of whether this script is run directly
# (`python ingestion/netcdf_reader.py`) or imported by server.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validation.file_validator import run_validation

KNOWN_ECV_PREFIXES = {
    # Ocean Color & Biogeochemistry
    "chlorophyll": ["chlor_a", "chl_ocx", "chl_a"],
    "reflectance": ["Rrs_", "Rrs"],
    "cdom": ["cdom_index", "cdom", "adg"],
    "poc": ["poc"],
    "tsm_ssc": ["tsm", "ssc"],
    "nflh": ["nflh"],
    # Physical Oceanography
    "sst": ["sst"],
    "ssh": ["ssh"],
    "sss": ["sss"],
    "osvw": ["wind_u", "wind_v", "osvw", "u", "v"],
    "sea_ice": ["sea_ice_conc", "sea_ice"],
    # Energy & Air-Sea Interaction
    "par": ["par", "ipar"],
    "aod": ["aot_", "aot", "angstrom"],
}


DATA_GROUP_CANDIDATES = ["geophysical_data"]
NAV_GROUP_CANDIDATES = ["navigation_data"]


class IngestionError(Exception):
    """Raised when a file can't be opened at all (missing, corrupted, unreadable)."""
    pass


def list_groups(file_path: str) -> list[str]:
    """Returns the names of all top-level netCDF4 groups in the file."""
    try:
        with netCDF4.Dataset(file_path, "r") as nc:
            return list(nc.groups.keys())
    except Exception as e:
        raise IngestionError(f"Failed to read group structure of '{Path(file_path).name}': {e}") from e


def open_dataset(file_path: str, group: str | None = None) -> xr.Dataset:
    """Opens a NetCDF/HDF file (optionally a specific group) via xarray."""
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
    groups = list_groups(file_path)
    data_group = next((g for g in DATA_GROUP_CANDIDATES if g in groups), None)
    nav_group = next((g for g in NAV_GROUP_CANDIDATES if g in groups), None)
    return data_group, nav_group


def extract_metadata(file_path: str) -> dict[str, Any]:
    data_group, nav_group = _find_data_and_nav_groups(file_path)
    root_ds = open_dataset(file_path)

    metadata: dict[str, Any] = {
        "structure": "grouped_swath" if data_group else "flat_grid",
        "global_attrs": dict(root_ds.attrs),
    }

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

    if "time_coverage_start" in root_ds.attrs:
        metadata["time_steps"] = [
            root_ds.attrs.get("time_coverage_start"),
            root_ds.attrs.get("time_coverage_end"),
        ]
        metadata["num_time_steps"] = 1
    elif "time" in root_ds.coords:
        time_vals = root_ds.coords["time"].values
        metadata["time_steps"] = [str(t) for t in time_vals]
        metadata["num_time_steps"] = len(time_vals)

    root_ds.close()
    return metadata


def identify_ecv_variables(file_path: str) -> dict[str, list[str]]:
    data_group, _ = _find_data_and_nav_groups(file_path)
    ds = open_dataset(file_path, group=data_group) if data_group else open_dataset(file_path)

    found: dict[str, list[str]] = {category: [] for category in KNOWN_ECV_PREFIXES}
    for var_name in ds.data_vars:
        for category, prefixes in KNOWN_ECV_PREFIXES.items():
            if any(var_name.startswith(p) or var_name == p for p in prefixes):
                found[category].append(var_name)

    ds.close()
    return found


def parse_file(file_path: str) -> dict[str, Any]:
    """
    Main entrypoint — opens a file (detecting flat vs. grouped structure
    automatically), extracts metadata and ECV classification, then runs
    the dedicated validator against the results.
    """
    path = Path(file_path)
    if not path.exists():
        raise IngestionError(f"File not found: {file_path}")

    metadata = extract_metadata(file_path)
    ecv_variables = identify_ecv_variables(file_path)
    validation_report = run_validation(metadata, ecv_variables)

    return {
        "file_name": path.name,
        "metadata": metadata,
        "ecv_variables": ecv_variables,
        "validation": validation_report.to_dict(),
    }


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) != 2:
        print("Usage: python netcdf_reader.py <path-to-netcdf-file>")
        sys.exit(1)

    try:
        result = parse_file(sys.argv[1])
        print(json.dumps(result, indent=2, default=str))
    except IngestionError as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)