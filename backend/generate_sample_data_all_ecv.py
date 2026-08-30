#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  2 18:08:58 2026

@author: akki2404
"""

"""
Extends Day 3's synthetic fixture (generate_sample_data.py) with the
remaining 7 ECVs not present in real MODIS-Aqua L2 OC files: CDOM,
TSM/SSC (Ocean Color/Biogeochemistry), SST, SSH, SSS, OSVW, Sea Ice
Concentration (Physical Oceanography). Same grid/time coords as Day 3's
fixture for consistency. Clearly synthetic — real satellite equivalents
for these 7 come from different missions/products (SST: MODIS SST L2,
SSH: Jason/Sentinel-6 altimetry, SSS: SMAP, OSVW: ASCAT, Sea Ice: AMSR2)
and are NOT covered by this fixture or the real_batch_data/ granules.
"""
import numpy as np
import xarray as xr
import pandas as pd
from config.paths import SAMPLE_ALL_ECV

lat = np.linspace(32.0, 38.0, 60)
lon = np.linspace(-125.0, -118.0, 70)
time = pd.date_range("2026-07-01", periods=3, freq="D")
rng = np.random.default_rng(42)
shape = (len(time), len(lat), len(lon))

def _masked(values, mask_frac=0.15):
    mask = rng.random(shape) < mask_frac
    values[mask] = np.nan
    return values

# CDOM (Colored Dissolved Organic Matter) — absorption coefficient, ~0-1 m^-1
cdom_index = _masked((rng.random(shape) * 1.0).astype("float32"))

# TSM/SSC (Total Suspended Matter / Suspended Sediment Concentration) — ~0-100 g/m^3
tsm = _masked((rng.lognormal(mean=1.5, sigma=1.0, size=shape)).astype("float32"))
tsm = np.clip(tsm, 0.1, 100.0)

# SST — realistic California-coast range in Celsius, ~10-22°C
sst = _masked((10 + rng.random(shape) * 12).astype("float32"))

# SSH — sea surface height anomaly, ~-0.5 to 0.5 m
ssh = _masked((rng.normal(0, 0.15, size=shape)).astype("float32"))

# SSS — sea surface salinity, ~32-37 PSU
sss = _masked((32 + rng.random(shape) * 5).astype("float32"))

# OSVW — Ocean Surface Vector Winds, as u/v components, ~-15 to 15 m/s
wind_u = _masked((rng.normal(0, 5, size=shape)).astype("float32"))
wind_v = _masked((rng.normal(0, 5, size=shape)).astype("float32"))

# Sea Ice Concentration — 0-100%, mostly 0 at this California latitude
# (kept nonzero/realistic-shaped for pipeline testing purposes only)
sea_ice_conc = _masked((rng.random(shape) * 100).astype("float32"))

ds = xr.Dataset(
    data_vars={
        "cdom_index": (("time", "lat", "lon"), cdom_index, {
            "long_name": "Colored Dissolved Organic Matter Index",
            "units": "m^-1",
        }),
        "tsm": (("time", "lat", "lon"), tsm, {
            "long_name": "Total Suspended Matter Concentration",
            "units": "g m^-3",
        }),
        "sst": (("time", "lat", "lon"), sst, {
            "long_name": "Sea Surface Temperature",
            "units": "degree_C",
        }),
        "ssh": (("time", "lat", "lon"), ssh, {
            "long_name": "Sea Surface Height Anomaly",
            "units": "m",
        }),
        "sss": (("time", "lat", "lon"), sss, {
            "long_name": "Sea Surface Salinity",
            "units": "PSU",
        }),
        "wind_u": (("time", "lat", "lon"), wind_u, {
            "long_name": "Eastward Ocean Surface Wind Component",
            "units": "m s^-1",
        }),
        "wind_v": (("time", "lat", "lon"), wind_v, {
            "long_name": "Northward Ocean Surface Wind Component",
            "units": "m s^-1",
        }),
        "sea_ice_conc": (("time", "lat", "lon"), sea_ice_conc, {
            "long_name": "Sea Ice Concentration",
            "units": "percent",
        }),
    },
    coords={
        "time": time,
        "lat": (("lat",), lat, {"units": "degrees_north", "long_name": "Latitude"}),
        "lon": (("lon",), lon, {"units": "degrees_east", "long_name": "Longitude"}),
    },
    attrs={
        "title": "Synthetic All-ECV Sample — OC-ECV Local Engine Day 19 test fixture",
        "institution": "OC-ECV Local Engine (synthetic test data, not real satellite data)",
        "source": "Generated for Day 19-21 full-ECV pipeline regression testing",
        "processing_level": "Synthetic L3-like",
        "note": "Covers the 7 ECVs not present in real MODIS-Aqua L2 OC granules "
                "(CDOM, TSM/SSC, SST, SSH, SSS, OSVW, Sea Ice Concentration). "
                "Real-data equivalents require separate satellite products/missions.",
    },
)

output_path = str(SAMPLE_ALL_ECV)
ds.to_netcdf(output_path)
print(f"All-ECV sample file written to: {output_path}")
print(f"Variables: {list(ds.data_vars.keys())}")