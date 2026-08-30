#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug  3 12:24:30 2026

@author: akki2404
"""

import earthaccess
from config.paths import REAL_SSS_DATA

auth = earthaccess.login(persist=True)

results = earthaccess.search_data(
    short_name="SMAP_RSS_L3_SSS_SMI_MONTHLY_V6",
    temporal=("2026-01-01", "2026-02-01"),
    count=1,
)

if not results:
    print("No granules found — try widening the date range.")
else:
    files = earthaccess.download(results, str(REAL_SSS_DATA))
    print(f"Downloaded: {files}")