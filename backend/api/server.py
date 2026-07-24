#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 23 20:45:51 2026

@author: akki2404
"""

"""
OC-ECV Local Engine — Backend Sidecar Entrypoint
Runs a local-loopback-only FastAPI server that the Tauri shell invokes
as a sidecar process. Never binds to 0.0.0.0 — 127.0.0.1 only, since
this must never be reachable from outside the local machine.
"""

import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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


if __name__ == "__main__":
    # Fixed port for now; Day 15+ (parameter-selection UI wiring) may need
    # dynamic port allocation if port conflicts become an issue.
    uvicorn.run(app, host="127.0.0.1", port=5321, log_level="info")