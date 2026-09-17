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
import rasterio
from rasterio.warp import transform_bounds
from rasterio.errors import RasterioIOError

# Ensure backend/ is on sys.path so `validation` resolves as a sibling
# package, regardless of whether this script is run directly
# (`python ingestion/netcdf_reader.py`) or imported by server.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validation.file_validator import run_validation

KNOWN_ECV_PREFIXES = {
    # Ocean Color & Biogeochemistry
    # ESA/Copernicus naming variants (CHL_OC4ME, CHL_NN, ADG443_NN,
    # TSM_NN) added Day 54, discovered via real Sentinel-3 OLCI GeoTIFF
    # testing -- first non-NASA-OB.DAAC provider tested in this
    # project. Matching itself is now case-insensitive (see
    # identify_ecv_variables/identify_ecv_variables_geotiff below), so
    # these entries only need to be listed once regardless of case.
    "chlorophyll": ["chlor_a", "chl_ocx", "chl_a", "chl_oc4me", "chl_nn", "cl-a", "chl"],
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
    "aod": ["aot_", "aot", "angstrom", "a865", "t865"],
}



DATA_GROUP_CANDIDATES = ["geophysical_data"]
NAV_GROUP_CANDIDATES = ["navigation_data"]

# Tier 1 GeoTIFF support (Day 54 prep) -- ingestion + metadata only.
# Full subsetting/stats/raster-rendering parity with NetCDF is NOT
# implemented; every downstream module (subsetting.py, statistics.py,
# raster.py) still assumes an xarray.Dataset with NetCDF-style
# variables/coords. Deliberate, documented scope limit -- see Day 54
# handover notes, not an oversight.
GEOTIFF_EXTENSIONS = {".tif", ".tiff"}


def _is_geotiff(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in GEOTIFF_EXTENSIONS


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
    if _is_geotiff(file_path):
        return extract_metadata_geotiff(file_path)
    
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
        lat_coord = next((c for c in root_ds.coords if c.lower() in ("lat", "latitude")), None)
        if lat_coord is not None:
            lat_vals = root_ds.coords[lat_coord].values
            # Some regular-grid products' coordinate arrays overshoot the
            # physical range by a fraction of a degree (float32 grid-step
            # rounding, e.g. 90.00015 instead of exactly 90) -- not real
            # data past the pole/antimeridian, just construction noise.
            # Clip the reported range (not the per-pixel data) so this
            # doesn't trip a false LAT/LON_OUT_OF_RANGE validation error.
            metadata["lat_range"] = [
                float(np.clip(lat_vals.min(), -90.0, 90.0)),
                float(np.clip(lat_vals.max(), -90.0, 90.0)),
            ]
        lon_coord = next((c for c in root_ds.coords if c.lower() in ("lon", "longitude")), None)
        if lon_coord is not None:
            lon_vals = root_ds.coords[lon_coord].values
            metadata["lon_range"] = [
                float(np.clip(lon_vals.min(), -180.0, 180.0)),
                float(np.clip(lon_vals.max(), -180.0, 180.0)),
            ]
        

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
    if _is_geotiff(file_path):
        band_names = extract_metadata(file_path)["variables"]
        return identify_ecv_variables_geotiff(file_path, band_names)
    
    data_group, _ = _find_data_and_nav_groups(file_path)
    ds = open_dataset(file_path, group=data_group) if data_group else open_dataset(file_path)

    found: dict[str, list[str]] = {category: [] for category in KNOWN_ECV_PREFIXES}
    for var_name in ds.data_vars:
        var_lower = var_name.lower()
        for category, prefixes in KNOWN_ECV_PREFIXES.items():
            if any(var_lower.startswith(p.lower()) or var_lower == p.lower() for p in prefixes):
                found[category].append(var_name)

    ds.close()
    return found

def extract_metadata_geotiff(file_path: str) -> dict[str, Any]:
    """
    Tier 1 GeoTIFF metadata extraction via rasterio directly (no new
    dependency -- rasterio has been installed since Day 1). Reprojects
    bounds to EPSG:4326 if the source CRS differs, since most
    real-world GeoTIFFs are NOT already lat/lon (commonly UTM or a
    sensor-native projection).
    """
    path = Path(file_path)
    if not path.exists():
        raise IngestionError(f"File not found: {file_path}")

    try:
        with rasterio.open(path) as src:
            width, height, band_count = src.width, src.height, src.count
            crs = src.crs
            bounds = src.bounds
            band_descriptions = list(src.descriptions)
            dtype = src.dtypes[0] if src.dtypes else None
            tags = src.tags()

            if crs is None:
                raise IngestionError(
                    f"GeoTIFF '{path.name}' has no CRS defined -- cannot determine geographic bounds."
                )

            if crs.to_epsg() == 4326:
                lon_min, lat_min, lon_max, lat_max = bounds.left, bounds.bottom, bounds.right, bounds.top
            else:
                lon_min, lat_min, lon_max, lat_max = transform_bounds(crs, "EPSG:4326", *bounds)
    except RasterioIOError as e:
        raise IngestionError(f"Failed to open GeoTIFF '{path.name}': {e}") from e

    band_names = [
        band_descriptions[i] if band_descriptions[i] else f"band_{i + 1}"
        for i in range(band_count)
    ]

    return {
        "structure": "geotiff_raster",
        "global_attrs": dict(tags),
        "dimensions": {"y": height, "x": width, "band": band_count},
        "variables": band_names,
        "coordinates": ["x", "y"],
        "lat_range": [float(lat_min), float(lat_max)],
        "lon_range": [float(lon_min), float(lon_max)],
        "source_crs": str(crs),
        "dtype": str(dtype),
    }


def identify_ecv_variables_geotiff(file_path: str, band_names: list[str]) -> dict[str, list[str]]:
    """
    GeoTIFF bands are frequently generic ("band_1", "band_2") with no
    descriptive name at all, unlike NetCDF variables -- so band-name
    matching alone often finds nothing even on a genuine ECV file.
    Falls back to checking the filename itself against the same known
    prefixes, attributing ALL bands to that category on a filename hit,
    rather than leaving a classifiable file with zero classified ECVs.
    """
    found: dict[str, list[str]] = {category: [] for category in KNOWN_ECV_PREFIXES}

    for var_name in band_names:
        var_lower = var_name.lower()
        for category, prefixes in KNOWN_ECV_PREFIXES.items():
            if any(var_lower.startswith(p.lower()) or var_lower == p.lower() for p in prefixes):
                found[category].append(var_name)
        

    if not any(found.values()):
        filename = Path(file_path).stem.lower()
        for category, prefixes in KNOWN_ECV_PREFIXES.items():
            if any(p.lower().rstrip("_") in filename for p in prefixes):
                found[category] = list(band_names)
                break

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