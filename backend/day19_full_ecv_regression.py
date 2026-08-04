#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  2 18:34:58 2026

@author: akki2404
"""

"""
Day 19: full pipeline regression across all 13 ECV categories, using the
real MODIS file for the 6 ECVs it covers, and sample_all_ecv.nc for the
remaining 7 synthetic ones.
"""
from processing.statistics import compute_regional_stats_cached, StatisticsError

REAL_FILE = "real_batch_data/AQUA_MODIS.20260101T092501.L2.OC.nc"
REAL_BBOX = (8, 15, 82, 90)  # confirmed-valid region, Day 8
REAL_VARS = ["chlor_a", "Rrs_443", "poc", "nflh", "par", "aot_869"]

SYNTH_FILE = "sample_all_ecv.nc"
SYNTH_BBOX = (33, 37, -124, -119)  # confirmed-valid sub-window, Day 16
SYNTH_VARS = ["cdom_index", "tsm", "sst", "ssh", "sss", "wind_u", "wind_v", "sea_ice_conc"]

def run_batch(file_path, bbox, variables, label):
    print(f"=== {label} ===")
    for var in variables:
        try:
            result = compute_regional_stats_cached(file_path, var, *bbox)
            print(f"  {var}: OK | valid_fraction={result.get('valid_fraction')} | "
                  f"mean={result.get('mean')} | cache_hit={result.get('_cache_hit')}")
        except StatisticsError as e:
            print(f"  {var}: FAILED — {e}")
        except Exception as e:
            print(f"  {var}: UNEXPECTED ERROR — {type(e).__name__}: {e}")

if __name__ == "__main__":
    run_batch(REAL_FILE, REAL_BBOX, REAL_VARS, "Real MODIS L2 OC file")
    run_batch(SYNTH_FILE, SYNTH_BBOX, SYNTH_VARS, "Synthetic all-ECV file")