#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  4 06:58:39 2026

@author: akki2404
"""

import earthaccess

auth = earthaccess.login(persist=True)

results = earthaccess.search_data(
    short_name="SWOT_L2_LR_SSH_D",
    temporal=("2026-01-01", "2026-01-05"),
    bounding_box=(82, 8, 90, 15),
    count=1,
)

if not results:
    print("No granules found.")
else:
    files = earthaccess.download(results, "./real_ssh_data")
    print(f"Downloaded: {files}")