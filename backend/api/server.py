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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn

from ingestion.netcdf_reader import parse_file, IngestionError
from processing.statistics import StatisticsError
from processing.quality_mask import QualityMaskError
from processing.statistics import compute_regional_stats_multivar, compute_regional_stats_cached
from processing.statistics import compute_batch_timeseries, compute_timeseries_within_file
from processing.statistics import compute_histogram, compute_scatter_correlation
from processing.raster import compute_regional_raster, RasterError
from processing.raw_export import compute_raw_export, RawExportError
from processing.temporal_filter import scan_directory_date_coverage, TemporalFilterError
from processing.geo_export import compute_geo_export, GeoExportError


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
    # /raster (Day 23) sends metadata via custom response headers instead
    # of a JSON body, to avoid a second round-trip for binary payloads.
    # Without explicitly exposing them, fetch() silently returns null for
    # these even though the server sent them correctly.
    expose_headers=[
        "X-Raster-Type", "X-Value-Min", "X-Value-Max",
        "X-Bounds", "X-Grid-Shape", "X-Point-Count",
        "X-Export-Kind",
    ],
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
        result = compute_regional_stats_cached(
            path, variable, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
        )
        return _sanitize(result)
    except (StatisticsError, QualityMaskError, IngestionError) as e:
        return {"error": str(e)}
    

@app.get("/raster")
def get_raster(
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
    Returns pixel-level data for WebGL raster rendering (Day 23), reusing
    the same subsetting/masking pipeline as /stats but returning an
    encoded binary payload instead of scalar statistics. Response shape
    depends on file structure (see X-Raster-Type header):
      - 'bitmap': flat-grid files — PNG bytes + X-Bounds, for BitmapLayer.
      - 'points': swath files — packed Float32 binary, for ScatterplotLayer.
    """
    flags_list = quality_flags.split(",") if quality_flags else None
    try:
        payload, raster_type, meta = compute_regional_raster(
            path, variable, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
        )
    except (StatisticsError, QualityMaskError, IngestionError, RasterError) as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    headers = {
        "X-Raster-Type": raster_type,
        "X-Value-Min": str(meta["value_min"]),
        "X-Value-Max": str(meta["value_max"]),
    }
    if raster_type == "bitmap":
        headers["X-Bounds"] = ",".join(str(b) for b in meta["bounds"])
        headers["X-Grid-Shape"] = ",".join(str(s) for s in meta["grid_shape"])
        return Response(content=payload, media_type="image/png", headers=headers)

    headers["X-Point-Count"] = str(meta["point_count"])
    return Response(content=payload, media_type="application/octet-stream", headers=headers)


@app.get("/export-raw")
def export_raw(
    path: str,
    variable: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    format: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    quality_flags: Optional[str] = None,
):
    """
    Day 37: raw numeric data export (.csv / .bin) at full physical-unit
    precision — the counterpart to /raster's rendering-oriented payloads.
    Same subsetting/masking pipeline as /stats and /raster; `format`
    (csv|bin) is the only new query parameter versus those endpoints.
    """
    flags_list = quality_flags.split(",") if quality_flags else None
    try:
        payload, media_type = compute_raw_export(
            path, variable, lat_min, lat_max, lon_min, lon_max, format,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
        )
    except (StatisticsError, QualityMaskError, IngestionError, RawExportError) as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    ext = "csv" if format == "csv" else "bin"
    headers = {"Content-Disposition": f'attachment; filename="oc-ecv-export.{ext}"'}
    return Response(content=payload, media_type=media_type, headers=headers)


@app.get("/export-geo")
def export_geo(
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
    Day 38: georeferenced raster export. Format is determined by file
    structure, not a caller choice — flat-grid exports as GeoTIFF,
    swath exports as CF-1.8 NetCDF (preserving native per-pixel geometry
    rather than regridding/interpolating onto a GeoTIFF-compatible grid).
    Same subsetting/masking pipeline as /stats, /raster, /export-raw.
    """
    flags_list = quality_flags.split(",") if quality_flags else None
    try:
        payload, media_type, export_kind = compute_geo_export(
            path, variable, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
        )
    except (StatisticsError, QualityMaskError, IngestionError, GeoExportError) as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    ext = "tif" if export_kind == "geotiff" else "nc"
    headers = {
        "Content-Disposition": f'attachment; filename="oc-ecv-export.{ext}"',
        "X-Export-Kind": export_kind,
    }
    return Response(content=payload, media_type=media_type, headers=headers)


@app.get("/timeseries-within-file")
def timeseries_within_file(
    path: str,
    variable: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Day 25: per-time-step regional statistics within a single flat-grid
    file's own time dimension, for within-file time-series trendlines —
    distinct from Day 17's /batch-timeseries, which series over multiple
    separate files rather than one file's own time steps.
    """
    try:
        result = compute_timeseries_within_file(
            path, variable, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date,
        )
        return _sanitize(result)
    except (StatisticsError, IngestionError) as e:
        return {"error": str(e)}

@app.get("/histogram")
def get_histogram(
    path: str,
    variable: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    quality_flags: Optional[str] = None,
    bins: int = 30,
):
    """
    Days 26-28: histogram (bin edges + counts) of valid pixel values for
    a variable over a bounding box — auxiliary plot alongside /stats.
    """
    flags_list = quality_flags.split(",") if quality_flags else None
    try:
        result = compute_histogram(
            path, variable, lat_min, lat_max, lon_min, lon_max,
            start_date=start_date, end_date=end_date, quality_flags=flags_list,
            bins=bins,
        )
        return _sanitize(result)
    except (StatisticsError, QualityMaskError, IngestionError) as e:
        return {"error": str(e)}


@app.get("/scatter")
def get_scatter(
    path: str,
    variable_x: str,
    variable_y: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    quality_flags: Optional[str] = None,
):
    """
    Days 26-28: paired (x, y) samples for two variables over the same
    bounding box, for scatter-plot parameter correlation.
    """
    flags_list = quality_flags.split(",") if quality_flags else None
    try:
        result = compute_scatter_correlation(
            path, variable_x, variable_y, lat_min, lat_max, lon_min, lon_max,
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
    
@app.get("/batch-date-coverage")
def batch_date_coverage(directory: str):
    try:
        result = scan_directory_date_coverage(directory)
        return json.loads(json.dumps(result, default=str))
    except TemporalFilterError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
if __name__ == "__main__":
    # Fixed port for now; may need dynamic port allocation later if port
    # conflicts become an issue.
    uvicorn.run(app, host="127.0.0.1", port=5321, log_level="info")