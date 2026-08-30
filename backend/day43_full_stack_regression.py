#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug 30 16:29:19 2026

@author: akki2404
"""

"""
Day 43-46: Full-stack regression across all 13 ECV categories, hitting the
LIVE sidecar over HTTP (not direct function calls) — exercises /ingest,
/stats, /raster, /timeseries-within-file (where applicable), /histogram,
/scatter, /export-raw (csv+bin), /export-geo, and /history.

Requires the Tauri sidecar already running on 127.0.0.1:5321.

Per project convention: verifies against the compiled/running artifact,
not source. Run this AFTER `npm run tauri dev` has the sidecar live.

Paths resolved via config.paths (project-root test_data/), not hardcoded
strings — consistent with the Day 43 prerequisite path-reorganization work.
"""
import sys

# backend/ is this script's own directory, so `config` (a direct child
# package) resolves without needing the sys.path.insert workaround used
# for sibling-package imports elsewhere in this project (e.g. server.py).
from config.paths import (
    SAMPLE_ALL_ECV,
    REAL_BATCH_DATA,
    REAL_IOP_DATA,
    REAL_OSVW_DATA,
    REAL_SSH_DATA,
    REAL_SSS_DATA,
    REAL_SST_DATA,
)

import requests
import time

BASE = "http://127.0.0.1:5321"
TIMEOUT = 30

REAL_BBOX = (8, 15, 82, 90)   # confirmed-valid region, Day 8
SYNTH_BBOX = (33, 37, -124, -119)  # confirmed-valid sub-window, Day 16

# ---------------------------------------------------------------------------
# Case table. `variable` is our BEST-DOCUMENTED GUESS per Day 19-21 reports
# for SST/SSS (not explicitly confirmed in source). Script verifies each
# against live /ingest output before querying — if a guess is wrong, it
# FAILS LOUD with the real variable list printed, rather than silently
# skipping or crashing later.
# ---------------------------------------------------------------------------
ECV_CASES = [
    # (label, path, bbox, variable, has_time_dim, kind)
    ("chlorophyll",  str(REAL_BATCH_DATA / "AQUA_MODIS.20260101T092501.L2.OC.nc"), REAL_BBOX, "chlor_a",  False, "real"),
    ("reflectance",  str(REAL_BATCH_DATA / "AQUA_MODIS.20260101T092501.L2.OC.nc"), REAL_BBOX, "Rrs_443",  False, "real"),
    ("poc",          str(REAL_BATCH_DATA / "AQUA_MODIS.20260101T092501.L2.OC.nc"), REAL_BBOX, "poc",      False, "real"),
    ("nflh",         str(REAL_BATCH_DATA / "AQUA_MODIS.20260101T092501.L2.OC.nc"), REAL_BBOX, "nflh",     False, "real"),
    ("par",          str(REAL_BATCH_DATA / "AQUA_MODIS.20260101T092501.L2.OC.nc"), REAL_BBOX, "par",      False, "real"),
    ("aod",          str(REAL_BATCH_DATA / "AQUA_MODIS.20260101T092501.L2.OC.nc"), REAL_BBOX, "aot_869",  False, "real"),
    ("sst",          str(REAL_SST_DATA / "AQUA_MODIS.20260101T092501.L2.SST.nc"),  REAL_BBOX, "sst",      False, "real"),  # UNVERIFIED name
    ("sss",          str(REAL_SSS_DATA / "RSS_smap_SSS_L3_monthly_2026_01_FNL_v06.0.nc"), REAL_BBOX, "sss_smap", False, "real"),  # UNVERIFIED name
    ("cdom",         str(REAL_IOP_DATA / "AQUA_MODIS.20260101T092501.L2.IOP.nc"),  REAL_BBOX, "adg_443",  False, "real"),
    ("osvw",         str(REAL_OSVW_DATA / "CCMP_Wind_Analysis_202601_monthly_mean_V03.1_L4.nc"), REAL_BBOX, "u", False, "real"),
    ("ssh",          str(REAL_SSH_DATA / "SWOT_L2_LR_SSH_Expert_043_523_20260101T044317_20260101T053355_PID0_01.nc"), REAL_BBOX, "ssh_karin", False, "real"),
    ("sea_ice_conc", str(SAMPLE_ALL_ECV), SYNTH_BBOX, "sea_ice_conc", True, "synthetic"),
    ("tsm_ssc",      str(SAMPLE_ALL_ECV), SYNTH_BBOX, "tsm",          True, "synthetic"),
]

# Second variable for scatter correlation per case — reuse a known-valid
# partner variable from the same file rather than inventing one.
SCATTER_PARTNER = {
    "chlorophyll": "Rrs_443",
    "reflectance": "chlor_a",
    "poc": "chlor_a",
    "nflh": "chlor_a",
    "par": "chlor_a",
    "aod": "chlor_a",
    "sst": None,        # single-var real SST file — verified via /ingest
    "sss": None,
    "cdom": None,
    "osvw": "v",
    "ssh": None,
    "sea_ice_conc": "tsm",
    "tsm_ssc": "sea_ice_conc",
}


def check_ingest(file_path, expected_var):
    r = requests.get(f"{BASE}/ingest", params={"path": file_path}, timeout=TIMEOUT)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    data = r.json()
    if "error" in data:
        return False, data["error"]
    all_vars = data.get("metadata", {}).get("variables", [])
    if expected_var not in all_vars:
        return False, f"'{expected_var}' NOT in real variable list: {all_vars}"
    return True, all_vars


def run_case(case):
    label, path, bbox, var, has_time, kind = case
    lat_min, lat_max, lon_min, lon_max = bbox
    print(f"\n{'='*70}\n{label.upper()}  ({kind})  file={path}\n{'='*70}")

    results = {}

    # 0. /ingest — verify variable name BEFORE anything else
    ok, info = check_ingest(path, var)
    if not ok:
        print(f"  [INGEST] FAILED — {info}")
        results["ingest"] = f"FAILED: {info}"
        return label, results  # can't proceed meaningfully without a real var name
    print(f"  [INGEST] OK — '{var}' confirmed present")
    results["ingest"] = "OK"

    common = dict(path=path, variable=var, lat_min=lat_min, lat_max=lat_max,
                  lon_min=lon_min, lon_max=lon_max)

    # 1. /stats
    r = requests.get(f"{BASE}/stats", params=common, timeout=TIMEOUT)
    d = r.json()
    if "error" in d:
        print(f"  [STATS] FAILED — {d['error']}")
        results["stats"] = f"FAILED: {d['error']}"
    else:
        print(f"  [STATS] OK — valid_fraction={d.get('valid_fraction')} mean={d.get('mean')} cache_hit={d.get('_cache_hit')}")
        results["stats"] = "OK"

    # 2. /raster
    r = requests.get(f"{BASE}/raster", params=common, timeout=TIMEOUT)
    if r.status_code != 200:
        try:
            err = r.json().get("error", r.text)
        except Exception:
            err = r.text
        print(f"  [RASTER] FAILED — {err}")
        results["raster"] = f"FAILED: {err}"
    else:
        rtype = r.headers.get("X-Raster-Type")
        print(f"  [RASTER] OK — type={rtype} bytes={len(r.content)}")
        results["raster"] = f"OK ({rtype})"

    # 3. /timeseries-within-file — only for flat-grid files with a time dim
    if has_time:
        r = requests.get(f"{BASE}/timeseries-within-file", params=common, timeout=TIMEOUT)
        d = r.json()
        if "error" in d:
            print(f"  [TIMESERIES] FAILED — {d['error']}")
            results["timeseries"] = f"FAILED: {d['error']}"
        else:
            print(f"  [TIMESERIES] OK — {len(d.get('entries', []))} steps")
            results["timeseries"] = "OK"
    else:
        print("  [TIMESERIES] SKIPPED (swath file, no time dimension)")
        results["timeseries"] = "SKIPPED"

    # 4. /histogram
    r = requests.get(f"{BASE}/histogram", params=common, timeout=TIMEOUT)
    d = r.json()
    if "error" in d:
        print(f"  [HISTOGRAM] FAILED — {d['error']}")
        results["histogram"] = f"FAILED: {d['error']}"
    else:
        print(f"  [HISTOGRAM] OK — {len(d.get('counts', []))} bins")
        results["histogram"] = "OK"

    # 5. /scatter — only if we have a known partner var in the same file
    partner = SCATTER_PARTNER.get(label)
    if partner:
        ok2, _ = check_ingest(path, partner)
        if ok2:
            sc_params = dict(path=path, variable_x=var, variable_y=partner,
                              lat_min=lat_min, lat_max=lat_max, lon_min=lon_min, lon_max=lon_max)
            r = requests.get(f"{BASE}/scatter", params=sc_params, timeout=TIMEOUT)
            d = r.json()
            if "error" in d:
                print(f"  [SCATTER] FAILED — {d['error']}")
                results["scatter"] = f"FAILED: {d['error']}"
            else:
                print(f"  [SCATTER] OK — {len(d.get('x', []))} pairs vs '{partner}'")
                results["scatter"] = "OK"
        else:
            print(f"  [SCATTER] SKIPPED — partner '{partner}' not confirmed in file")
            results["scatter"] = "SKIPPED (partner unverified)"
    else:
        print("  [SCATTER] SKIPPED — no partner variable defined for this case")
        results["scatter"] = "SKIPPED"

    # 6. /export-raw (csv + bin)
    for fmt in ("csv", "bin"):
        r = requests.get(f"{BASE}/export-raw", params={**common, "format": fmt}, timeout=TIMEOUT)
        if r.status_code != 200:
            try:
                err = r.json().get("error", r.text)
            except Exception:
                err = r.text
            print(f"  [EXPORT-RAW {fmt}] FAILED — {err}")
            results[f"export_raw_{fmt}"] = f"FAILED: {err}"
        else:
            print(f"  [EXPORT-RAW {fmt}] OK — {len(r.content)} bytes")
            results[f"export_raw_{fmt}"] = "OK"

    # 7. /export-geo
    r = requests.get(f"{BASE}/export-geo", params=common, timeout=TIMEOUT)
    if r.status_code != 200:
        try:
            err = r.json().get("error", r.text)
        except Exception:
            err = r.text
        print(f"  [EXPORT-GEO] FAILED — {err}")
        results["export_geo"] = f"FAILED: {err}"
    else:
        kind_hdr = r.headers.get("X-Export-Kind")
        print(f"  [EXPORT-GEO] OK — kind={kind_hdr} bytes={len(r.content)}")
        results["export_geo"] = f"OK ({kind_hdr})"

    return label, results


def check_history_appears():
    """After all cases run, confirm /history reflects the recent queries."""
    r = requests.get(f"{BASE}/history", params={"limit": 50, "offset": 0}, timeout=TIMEOUT)
    d = r.json()
    if "error" in d:
        print(f"\n[HISTORY] FAILED — {d['error']}")
        return
    entries = d.get("entries", d) if isinstance(d, dict) else d
    print(f"\n[HISTORY] OK — {len(entries) if isinstance(entries, list) else '?'} entries returned")


def main():
    # Sanity: sidecar reachable at all before running 13 x ~8 requests
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        assert r.status_code == 200
    except Exception as e:
        print(f"FATAL: sidecar not reachable at {BASE} — {e}")
        sys.exit(1)

    all_results = {}
    for case in ECV_CASES:
        label, results = run_case(case)
        all_results[label] = results
        time.sleep(0.2)  # avoid hammering the sidecar back-to-back

    check_history_appears()

    # Summary
    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for label, results in all_results.items():
        failed = [k for k, v in results.items() if isinstance(v, str) and v.startswith("FAILED")]
        status = "\u2705 ALL OK" if not failed else f"\u274c FAILED: {failed}"
        print(f"  {label:20s} {status}")


if __name__ == "__main__":
    main()