#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jul 25 05:04:10 2026

@author: akki2404
"""

"""
Generates a synthetic sample NetCDF file mimicking NASA Ocean Color L2/L3
structure — used to test the ingestion pipeline without needing an
Earthdata login to download a real file.

Variables included: chlor_a (Chl-a), Rrs_443, Rrs_555 (Remote Sensing
Reflectance at two common wavelengths), plus lat/lon/time coordinates
and quality-flag-style attributes, matching real OB.DAAC file conventions
closely enough for ingestion/parsing logic to be developed and tested
against realistic structure.
"""

import numpy as np
import xarray as xr
import pandas as pd
from config.paths import SAMPLE_OCEANCOLOR

# Spatial grid — a small region, e.g. off the California coast
lat = np.linspace(32.0, 38.0, 60)
lon = np.linspace(-125.0, -118.0, 70)
time = pd.date_range("2026-07-01", periods=3, freq="D")

rng = np.random.default_rng(42)

# Chlorophyll-a: realistic range ~0.01–20 mg/m^3, log-normal-ish distribution
chlor_a = rng.lognormal(mean=0.5, sigma=1.0, size=(len(time), len(lat), len(lon))).astype("float32")
chlor_a = np.clip(chlor_a, 0.01, 20.0)

# Remote sensing reflectance at two wavelengths — realistic range ~0–0.02 sr^-1
rrs_443 = (rng.random((len(time), len(lat), len(lon))) * 0.015).astype("float32")
rrs_555 = (rng.random((len(time), len(lat), len(lon))) * 0.010).astype("float32")

# Simulate some cloud/land masking with NaNs, like real quality-flagged data
mask = rng.random((len(time), len(lat), len(lon))) < 0.15
chlor_a[mask] = np.nan
rrs_443[mask] = np.nan
rrs_555[mask] = np.nan

ds = xr.Dataset(
    data_vars={
        "chlor_a": (("time", "lat", "lon"), chlor_a, {
            "long_name": "Chlorophyll Concentration, OCx Algorithm",
            "units": "mg m^-3",
            "valid_min": 0.001,
            "valid_max": 100.0,
        }),
        "Rrs_443": (("time", "lat", "lon"), rrs_443, {
            "long_name": "Remote Sensing Reflectance at 443 nm",
            "units": "sr^-1",
        }),
        "Rrs_555": (("time", "lat", "lon"), rrs_555, {
            "long_name": "Remote Sensing Reflectance at 555 nm",
            "units": "sr^-1",
        }),
    },
    coords={
        "time": time,
        "lat": (("lat",), lat, {"units": "degrees_north", "long_name": "Latitude"}),
        "lon": (("lon",), lon, {"units": "degrees_east", "long_name": "Longitude"}),
    },
    attrs={
        "title": "Synthetic Ocean Color Sample — OC-ECV Local Engine test fixture",
        "institution": "OC-ECV Local Engine (synthetic test data, not real satellite data)",
        "source": "Generated for Day 3 ingestion pipeline testing",
        "processing_level": "Synthetic L3-like",
    },
)

output_path = str(SAMPLE_OCEANCOLOR)
ds.to_netcdf(output_path)
print(f"Sample file written to: {output_path}")
print(ds)