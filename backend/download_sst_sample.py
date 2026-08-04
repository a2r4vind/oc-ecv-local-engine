#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug  3 06:36:15 2026

@author: akki2404
"""

import earthaccess

auth = earthaccess.login(persist=True)

# Same swath pass as the existing OC granule (2026-01-01T09:25:01Z) —
# Arabian Sea / India's west coast, so this SST file should have real
# spatial overlap with real_batch_data's first OC granule
results = earthaccess.search_data(
    short_name="MODISA_L2_SST",
    temporal=("2026-01-01", "2026-01-02"),
    bounding_box=(82, 8, 90, 15),
    count=1,
)

if not results:
    print("No granules found — try widening the date range or bounding box.")
else:
    files = earthaccess.download(results, "./real_sst_data")
    print(f"Downloaded: {files}")