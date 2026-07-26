#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 26 11:57:08 2026

@author: akki2404
"""

"""
Benchmarks the ingestion pipeline against a given file, timing each stage
separately (group listing, metadata extraction, ECV classification,
validation) so we can see exactly where time is spent on large files —
rather than just a single end-to-end number.

Usage: python benchmark_ingestion.py <path-to-file>
"""

import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion.netcdf_reader import (
    list_groups,
    extract_metadata,
    identify_ecv_variables,
)
from validation.file_validator import run_validation


def benchmark(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    file_size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Benchmarking: {path.name} ({file_size_mb:.1f} MB on disk)\n")

    tracemalloc.start()
    total_start = time.perf_counter()

    t0 = time.perf_counter()
    groups = list_groups(file_path)
    t1 = time.perf_counter()
    print(f"list_groups():           {t1 - t0:.3f}s  -> groups: {groups}")

    t0 = time.perf_counter()
    metadata = extract_metadata(file_path)
    t1 = time.perf_counter()
    print(f"extract_metadata():      {t1 - t0:.3f}s")

    t0 = time.perf_counter()
    ecv_vars = identify_ecv_variables(file_path)
    t1 = time.perf_counter()
    print(f"identify_ecv_variables(): {t1 - t0:.3f}s")

    t0 = time.perf_counter()
    validation = run_validation(metadata, ecv_vars)
    t1 = time.perf_counter()
    print(f"run_validation():        {t1 - t0:.3f}s")

    total_elapsed = time.perf_counter() - total_start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\nTotal ingestion time:    {total_elapsed:.3f}s")
    print(f"Peak Python memory used: {peak / (1024 * 1024):.1f} MB")
    error_count = sum(1 for i in validation.issues if i.severity == "error")
    warning_count = sum(1 for i in validation.issues if i.severity == "warning")
    print(f"Validation result:       valid={validation.valid}, "
          f"errors={error_count}, warnings={warning_count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python benchmark_ingestion.py <path-to-netcdf-file>")
        sys.exit(1)

    benchmark(sys.argv[1])