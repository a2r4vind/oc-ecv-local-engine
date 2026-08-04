#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 06:47:30 2026

@author: akki2404
"""

import earthaccess

auth = earthaccess.login(persist=True)

results = earthaccess.search_data(
    short_name="CCMP_WINDS_10MMONTHLY_L4_V3.1",
    temporal=("2026-01-01", "2026-02-01"),
    count=1,
)

if not results:
    print("No granules found.")
else:
    files = earthaccess.download(results, "./real_osvw_data")
    print(f"Downloaded: {files}")