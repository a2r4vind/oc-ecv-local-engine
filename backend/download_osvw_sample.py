#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 06:47:30 2026

@author: akki2404
"""

import earthaccess
from config.paths import REAL_OSVW_DATA

auth = earthaccess.login(persist=True)

results = earthaccess.search_data(
    short_name="CCMP_WINDS_10MMONTHLY_L4_V3.1",
    temporal=("2026-01-01", "2026-02-01"),
    count=1,
)

if not results:
    print("No granules found.")
else:
    files = earthaccess.download(results, str(REAL_OSVW_DATA))
    print(f"Downloaded: {files}")