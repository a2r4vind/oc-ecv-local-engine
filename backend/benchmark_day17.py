#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 30 12:10:05 2026

@author: akki2404
"""

"""Tests compute_batch_timeseries() across the real 25-file MODIS batch,
comparing serialize_file_access=True vs False across repeated trials —
proving (not assuming) whether cross-file HDF5 concurrency is safe."""
import time
from processing.statistics import compute_batch_timeseries

DIRECTORY = "real_batch_data"
VARIABLE = "chlor_a"
BBOX = (8, 15, 82, 90)  # Day 8's confirmed-valid Bay of Bengal region
START_DATE = "2026-01-01"
END_DATE = "2026-07-31"  # wide enough to cover all 25 real_batch_data files

def run_trial(serialize: bool):
    t0 = time.perf_counter()
    result = compute_batch_timeseries(
        DIRECTORY, VARIABLE, *BBOX, 
        start_date=START_DATE, end_date=END_DATE,
        serialize_file_access=serialize
    )
    elapsed = time.perf_counter() - t0
    errors = [e for e in result["timeseries"] if "error" in e]
    return elapsed, len(errors), result["file_count"]

if __name__ == "__main__":
    print("=== serialize_file_access=True (safe baseline) ===")
    for i in range(10):
        t, errs, n = run_trial(serialize=True)
        print(f"Trial {i+1}: {t:.2f}s | {n} files | {errs} errors")

    print("\n=== serialize_file_access=False (testing cross-file concurrency) ===")
    for i in range(10):
        t, errs, n = run_trial(serialize=False)
        print(f"Trial {i+1}: {t:.2f}s | {n} files | {errs} errors")