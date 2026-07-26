#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 26 13:22:52 2026

@author: akki2404
"""

"""
Runs the ingestion pipeline across every file in a directory, reporting
per-file and cumulative timing/size stats — a realistic multi-GB stress
test built from many real satellite granules rather than one giant file,
since individual Ocean Color L2 products only run ~100-150MB each.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingestion.netcdf_reader import parse_file, IngestionError


def batch_benchmark(directory: str):
    dir_path = Path(directory)
    files = sorted(dir_path.glob("*.nc"))

    if not files:
        print(f"No .nc files found in {directory}")
        sys.exit(1)

    print(f"Found {len(files)} files in {directory}\n")

    total_size_mb = 0.0
    total_time = 0.0
    results = []

    for f in files:
        size_mb = f.stat().st_size / (1024 * 1024)
        start = time.perf_counter()
        try:
            result = parse_file(str(f))
            valid = result["validation"]["valid"]
            error = None
        except IngestionError as e:
            valid = False
            error = str(e)
        elapsed = time.perf_counter() - start

        total_size_mb += size_mb
        total_time += elapsed
        results.append((f.name, size_mb, elapsed, valid, error))

        status = "OK" if valid else f"FAILED ({error})" if error else "INVALID"
        print(f"{f.name:55s} {size_mb:7.1f} MB  {elapsed:6.2f}s  {status}")

    print(f"\n{'=' * 80}")
    print(f"Total files processed:  {len(files)}")
    print(f"Total data volume:      {total_size_mb / 1024:.2f} GB")
    print(f"Total ingestion time:   {total_time:.2f}s")
    print(f"Average throughput:     {total_size_mb / total_time:.1f} MB/s")
    print(f"Average time per file:  {total_time / len(files):.2f}s")

    failures = [r for r in results if r[4] is not None]
    if failures:
        print(f"\n{len(failures)} file(s) failed to ingest:")
        for name, _, _, _, error in failures:
            print(f"  - {name}: {error}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python batch_benchmark.py <directory-of-nc-files>")
        sys.exit(1)

    batch_benchmark(sys.argv[1])