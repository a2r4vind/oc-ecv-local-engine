"""
OC-ECV Local Engine — Backend Sidecar Entrypoint
Runs a local-loopback-only FastAPI server that the Tauri shell invokes
as a sidecar process. Never binds to 0.0.0.0 — 127.0.0.1 only, since
this must never be reachable from outside the local machine.
"""

import sys
import json
from pathlib import Path
from typing import Optional

# Ensure backend/ is on sys.path so `ingestion`/`processing` resolve as
# packages, regardless of the working directory this script is launched
# from (matters both for `python api/server.py` and the PyInstaller-frozen binary).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from ingestion.netcdf_reader import parse_file, IngestionError
from processing.statistics import compute_regional_stats, StatisticsError
from processing.quality_mask import QualityMaskError
from processing.statistics import compute_regional_stats_multivar
from processing.statistics import compute_batch_timeseries


app = FastAPI(title="OC-ECV Local Engine Backend")

# Tauri's webview origin varies by OS (tauri://localhost on Linux/macOS,
# https://tauri.localhost on Windows) — allow both for local dev safety.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "https://tauri.localhost",
        "http://localhost:1420",  # Vite dev server, for `tauri dev`
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sanitize(result: dict) -> dict:
    """
    Sanitizes any non-JSON-native types (e.g. numpy scalars) before
    FastAPI serializes the response — same safety net used since Day 5,
    since real satellite file metadata/values often include numpy types
    that FastAPI's built-in encoder can't handle natively.
    """
    return json.loads(json.dumps(result, default=str))


@app.get("/health")
def health_check():
    """Sanity check endpoint — confirms the sidecar is alive and reachable."""
    return {"status": "ok", "service": "oc-ecv-backend"}


@app.get("/version")
def version():
    return {"python_version": sys.version, "engine": "oc-ecv-local-engine"}


@app.get("/diagnostics")
def diagnostics():
    """Verifies heavy geospatial dependencies actually load inside this process —
    critical to check specifically in the PyInstaller-bundled binary, since GDAL's
    dynamically-loaded drivers/data files are easy for PyInstaller to miss."""
    results = {}
    try:
        from osgeo import gdal
        results["gdal"] = gdal.__version__
    except Exception as e:
        results["gdal_error"] = str(e)
    try:
        import netCDF4
        results["netCDF4"] = netCDF4.__version__
    except Exception as e:
        results["netCDF4_error"] = str(e)
    try:
        import rasterio
        results["rasterio"] = rasterio.__version__
    except Exception as e:
        results["rasterio_error"] = str(e)
    try:
        import xarray
        results["xarray"] = xarray.__version__
    except Exception as e:
        results["xarray_error"] = str(e)
    return results


@app.get("/ingest")
def ingest_file(path: str):
    """
    Parses a local NetCDF/HDF file and returns its metadata, ECV variable
    classification, and validation results. `path` is an absolute file
    path selected via the frontend's file dialog.
    """
    try:
        result = parse_file(path)
        return _sanitize(result)
    except IngestionError as e:
        return {"error": str(e)}


@app.get("/stats")
def get_stats(
    path: str,
    variable: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    quality_flags: Optional[str] = None,
):
    """
    Computes regional statistics (mean/min/max/std) for a variable over a
    bounding box, with optional temporal filtering (flat-grid files) or
    quality-flag masking (swath files) — the endpoint the Days 12-14
    parameter-selection UI's "Run Query" button calls.

    `quality_flags` is a comma-separated string (e.g. "LAND,CLDICE") since
    query parameters are flat strings, not native lists.
    """
    flags_list = quality_flags.split(",") if quality_flags else None

    try:
        result = compute_regional_stats(
            path, variable, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
        )
        return _sanitize(result)
    except (StatisticsError, QualityMaskError, IngestionError) as e:
        return {"error": str(e)}
    

@app.get("/stats-multi")
def stats_multi(
    path: str,
    variables: str,  # comma-separated, e.g. "chlor_a,Rrs_443,Rrs_555"
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: str | None = None,
):
    var_list = [v.strip() for v in variables.split(",")]
    flags_list = quality_flags.split(",") if quality_flags else None
    try:
        result = compute_regional_stats_multivar(
            path, var_list, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
        )
        return json.loads(json.dumps(result, default=str))  # same NumPy-scalar sanitization as Day 5
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/batch-timeseries")
def batch_timeseries(
    directory: str,
    variable: str,
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
    start_date: str | None = None,
    end_date: str | None = None,
    quality_flags: str | None = None,
    serialize_file_access: bool = True,
):
    flags_list = quality_flags.split(",") if quality_flags else None
    try:
        result = compute_batch_timeseries(
            directory, variable, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
            serialize_file_access=serialize_file_access,
        )
        return json.loads(json.dumps(result, default=str))
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
if __name__ == "__main__":
    # Fixed port for now; may need dynamic port allocation later if port
    # conflicts become an issue.
    uvicorn.run(app, host="127.0.0.1", port=5321, log_level="info")