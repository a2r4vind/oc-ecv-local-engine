#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 26 11:46:38 2026

@author: akki2404
"""

"""
Generates a large (multi-GB) synthetic Ocean Color-style NetCDF file for
stress-testing the ingestion pipeline's parsing speed and memory behavior.

Writes data time-slice by time-slice directly via netCDF4 (not building
the full array in memory via xarray/NumPy first) so RAM usage stays
bounded regardless of total file size — this mirrors how you'd need to
handle truly large satellite products in Phase 2's processing pipeline.
"""

import time
import numpy as np
import netCDF4

# Tune these to control final file size. Rough size estimate:
# TIME * LAT * LON * 4 bytes (float32) * NUM_VARS
# Default below: 10 * 4000 * 5000 * 4 * 3 vars ≈ 2.4 GB
TIME_STEPS = 10
LAT_SIZE = 4000
LON_SIZE = 5000
OUTPUT_PATH = "large_sample_oceancolor.nc"

rng = np.random.default_rng(42)


def main():
    print(f"Generating {OUTPUT_PATH}: {TIME_STEPS} x {LAT_SIZE} x {LON_SIZE} grid...")
    start = time.perf_counter()

    nc = netCDF4.Dataset(OUTPUT_PATH, "w", format="NETCDF4")

    nc.createDimension("time", TIME_STEPS)
    nc.createDimension("lat", LAT_SIZE)
    nc.createDimension("lon", LON_SIZE)

    lat_var = nc.createVariable("lat", "f8", ("lat",))
    lon_var = nc.createVariable("lon", "f8", ("lon",))
    lat_var[:] = np.linspace(32.0, 38.0, LAT_SIZE)
    lon_var[:] = np.linspace(-125.0, -118.0, LON_SIZE)
    lat_var.units = "degrees_north"
    lon_var.units = "degrees_east"

    chlor_a = nc.createVariable(
        "chlor_a", "f4", ("time", "lat", "lon"),
        zlib=True, complevel=4,  # compression keeps on-disk size reasonable
        chunksizes=(1, LAT_SIZE, LON_SIZE),
    )
    chlor_a.long_name = "Chlorophyll Concentration, OCx Algorithm"
    chlor_a.units = "mg m^-3"

    rrs_443 = nc.createVariable(
        "Rrs_443", "f4", ("time", "lat", "lon"),
        zlib=True, complevel=4,
        chunksizes=(1, LAT_SIZE, LON_SIZE),
    )
    rrs_443.long_name = "Remote Sensing Reflectance at 443 nm"
    rrs_443.units = "sr^-1"

    rrs_555 = nc.createVariable(
        "Rrs_555", "f4", ("time", "lat", "lon"),
        zlib=True, complevel=4,
        chunksizes=(1, LAT_SIZE, LON_SIZE),
    )
    rrs_555.long_name = "Remote Sensing Reflectance at 555 nm"
    rrs_555.units = "sr^-1"

    nc.title = "Large Synthetic Ocean Color Sample — Day 6-7 stress test fixture"
    nc.institution = "OC-ECV Local Engine (synthetic test data, not real satellite data)"

    # Write one time slice at a time — bounds memory to one slice's worth
    # of data per variable (LAT_SIZE * LON_SIZE * 4 bytes ≈ tens of MB),
    # regardless of how many time steps the total file has.
    for t in range(TIME_STEPS):
        slice_start = time.perf_counter()

        chl_slice = rng.lognormal(mean=0.5, sigma=1.0, size=(LAT_SIZE, LON_SIZE)).astype("float32")
        rrs443_slice = (rng.random((LAT_SIZE, LON_SIZE)) * 0.015).astype("float32")
        rrs555_slice = (rng.random((LAT_SIZE, LON_SIZE)) * 0.010).astype("float32")

        mask = rng.random((LAT_SIZE, LON_SIZE)) < 0.15
        chl_slice[mask] = np.nan
        rrs443_slice[mask] = np.nan
        rrs555_slice[mask] = np.nan

        chlor_a[t, :, :] = chl_slice
        rrs_443[t, :, :] = rrs443_slice
        rrs_555[t, :, :] = rrs555_slice

        print(f"  Time step {t + 1}/{TIME_STEPS} written in {time.perf_counter() - slice_start:.2f}s")

    nc.close()

    elapsed = time.perf_counter() - start
    print(f"\nDone in {elapsed:.2f}s")


if __name__ == "__main__":
    main()