#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 06:28:20 2026

@author: akki2404
"""

import earthaccess

auth = earthaccess.login(persist=True)

# Same swath pass as existing OC/SST granules (2026-01-01T09:25:01Z) —
# Arabian Sea / India's west coast, IOP product carries CDOM (adg_*) data
results = earthaccess.search_data(
    short_name="MODISA_L2_IOP",
    temporal=("2026-01-01", "2026-01-02"),
    bounding_box=(82, 8, 90, 15),
    count=1,
)

if not results:
    print("No granules found — try widening the date range or bounding box.")
else:
    files = earthaccess.download(results, "./real_iop_data")
    print(f"Downloaded: {files}")