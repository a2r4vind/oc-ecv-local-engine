from __future__ import annotations
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 31 18:34:14 2026

@author: akki2404
"""

"""
Day 44 — Memory leak detection session.

Samples RSS for the Tauri webview process and the oc-ecv-backend sidecar
(including PyInstaller --onefile bootloader children) at a fixed interval,
logs to CSV, and reports a simple linear-trend summary at the end.

Two modes:

  monitor        Passive sampling only. Run this ALONGSIDE the manual
                  frontend stress checklist (docs/Day_44_Frontend_Checklist.md)
                  — you drive the UI by hand, this just watches RSS. This is
                  the mode that can actually implicate/rule out issue #4
                  (DeckGLOverlay/useControl canvas cleanup), since that only
                  happens through real mount/unmount cycles in the running
                  app, not through backend calls alone.

  backend-stress  Active mode. Drives repeated HTTP requests directly against
                  the sidecar (ingest -> stats -> raster -> timeseries ->
                  histogram -> scatter) for N cycles, no UI involved. Use
                  this to isolate whether any growth is sidecar-side (cache
                  table growth, PyInstaller bootloader child accumulation,
                  etc.) completely decoupled from the webview/deck.gl.

Usage:
  python day44_memory_leak_session.py --mode monitor --duration-min 30
  python day44_memory_leak_session.py --mode backend-stress --cycles 30

IMPORTANT — verify before first run:
  - SIDECAR_NAME_HINT below assumes the compiled binary's process name/
    cmdline contains "oc-ecv-backend" (matches the rebuild routine's output
    filename). Confirmed reasonable, not independently re-verified this
    session.
  - Path resolution now correctly imports REAL_BATCH_DATA directly from
    backend/config/paths.py (verified against actual source this session —
    the earlier draft had guessed a non-existent TEST_DATA_REAL_DIR name).
  - WEBVIEW_NAME_HINT is a PLACEHOLDER ("oc-ecv-local-engine") — Tauri dev
    spawns the compiled Rust binary, whose name comes from tauri.conf.json /
    Cargo.toml `package.name`, which I don't have in front of me. Run
    `ps aux | grep target/debug` while `npm run tauri dev` is running and
    correct this constant (or pass --webview-name) before trusting any
    webview RSS numbers.

Requires `psutil` (and `requests` for backend-stress mode). psutil is a
C-extension package; per this project's established convention for
compiled/ABI-sensitive packages, install via:
    conda install -n oc-ecv-env -c conda-forge psutil requests
rather than pip, to stay consistent with how rasterio/netCDF4/h5py etc.
are installed in this environment.
"""
# from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil

# --- Path resolution -------------------------------------------------------
# Attempts to reuse the project's centralized path resolver (per the
# project's "never hardcode relative paths to test data" convention).
# Falls back to a local guess if paths.py's actual exported names differ
# from what's assumed here — VERIFY this import resolves cleanly before
# trusting REAL_DATA_DIR below; if it fails silently to the fallback,
# --files-dir should be passed explicitly instead.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config.paths import REAL_BATCH_DATA  # type: ignore
    _PATHS_IMPORT_OK = True
except Exception:
    REAL_BATCH_DATA = Path(__file__).resolve().parent.parent / "test_data" / "real" / "real_batch_data"
    _PATHS_IMPORT_OK = False

LOG_DIR = Path(__file__).resolve().parent.parent / "docs" / "memory_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SIDECAR_NAME_HINT = "oc-ecv-backend"
WEBVIEW_NAME_HINT = "oc-ecv-local-engine"  # PLACEHOLDER — verify, see docstring

SIDECAR_BASE_URL = "http://127.0.0.1:5321"


# --- Process discovery -------------------------------------------------------

def find_processes(name_hint: str) -> list[psutil.Process]:
    """Return all live processes whose name or cmdline contains name_hint."""
    matches = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = proc.info.get("name") or ""
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if name_hint in name or name_hint in cmdline:
                matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matches


def total_rss_bytes(name_hint: str) -> Optional[int]:
    """
    Sum RSS across every live process matching name_hint AND all of its
    descendants (recursive) — necessary because PyInstaller --onefile
    binaries run a bootloader that forks a child process at runtime; a
    single-PID reading can silently miss the process actually holding the
    memory.
    """
    procs = find_processes(name_hint)
    if not procs:
        return None
    total = 0
    seen_pids = set()
    for p in procs:
        try:
            for target in [p] + p.children(recursive=True):
                if target.pid in seen_pids:
                    continue
                seen_pids.add(target.pid)
                total += target.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total


# --- Sampling ----------------------------------------------------------------

@dataclass
class Sample:
    timestamp: str
    elapsed_s: float
    cycle: int
    webview_rss_mb: Optional[float]
    sidecar_rss_mb: Optional[float]


@dataclass
class Session:
    samples: list[Sample] = field(default_factory=list)

    def record(self, cycle: int, start_time: float, webview_hint: str, sidecar_hint: str):
        webview_rss = total_rss_bytes(webview_hint)
        sidecar_rss = total_rss_bytes(sidecar_hint)
        self.samples.append(
            Sample(
                timestamp=datetime.now().isoformat(timespec="seconds"),
                elapsed_s=round(time.time() - start_time, 1),
                cycle=cycle,
                webview_rss_mb=round(webview_rss / 1e6, 2) if webview_rss is not None else None,
                sidecar_rss_mb=round(sidecar_rss / 1e6, 2) if sidecar_rss is not None else None,
            )
        )

    def write_csv(self, path: Path):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "elapsed_s", "cycle", "webview_rss_mb", "sidecar_rss_mb"])
            for s in self.samples:
                writer.writerow([s.timestamp, s.elapsed_s, s.cycle, s.webview_rss_mb, s.sidecar_rss_mb])

    def summarize(self):
        def trend(values: list[Optional[float]]) -> Optional[dict]:
            clean = [(i, v) for i, v in enumerate(values) if v is not None]
            if len(clean) < 3:
                return None
            xs = [i for i, _ in clean]
            ys = [v for _, v in clean]
            n = len(xs)
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
            den = sum((x - mean_x) ** 2 for x in xs) or 1e-9
            slope = num / den  # MB per sample
            return {
                "min_mb": min(ys),
                "max_mb": max(ys),
                "first_mb": ys[0],
                "last_mb": ys[-1],
                "growth_mb": round(ys[-1] - ys[0], 2),
                "slope_mb_per_sample": round(slope, 4),
            }

        print("\n" + "=" * 72)
        print(f"SESSION SUMMARY — {len(self.samples)} samples")
        print("=" * 72)

        for label, values in [
            ("Webview", [s.webview_rss_mb for s in self.samples]),
            ("Sidecar (incl. children)", [s.sidecar_rss_mb for s in self.samples]),
        ]:
            t = trend(values)
            if t is None:
                print(f"\n{label}: insufficient data (process not found across enough samples)")
                continue
            print(f"\n{label}:")
            print(f"  first={t['first_mb']} MB  last={t['last_mb']} MB  "
                  f"min={t['min_mb']} MB  max={t['max_mb']} MB")
            print(f"  net growth over session: {t['growth_mb']} MB")
            print(f"  linear trend: {t['slope_mb_per_sample']} MB/sample")
            # Heuristic flag only — a real verdict needs eyeballing the CSV/
            # plot, not a single threshold. Sawtooth (grow-then-GC) patterns
            # are normal and would show a shallow slope despite real
            # allocation churn; a suspicious pattern is monotonic growth
            # with near-zero subsequent drops.
            if t["slope_mb_per_sample"] > 0.5:
                print("  ⚠ sustained upward trend — inspect CSV for monotonic "
                      "(non-sawtooth) growth before concluding a leak")
            else:
                print("  no strong sustained upward trend detected")
                
        if not _PATHS_IMPORT_OK:
            print("\n⚠ Note: config.paths import fell back to a guessed path — "
                  "REAL_BATCH_DATA may be wrong if used in backend-stress mode.")



# --- Mode: monitor -------------------------------------------------------

def run_monitor(duration_min: float, interval_s: float, webview_hint: str, sidecar_hint: str):
    print(f"Monitoring for {duration_min} min, sampling every {interval_s}s.")
    print("Drive the UI manually per the Day 44 frontend checklist now.")
    print("Press Ctrl+C to stop early and still get a summary + CSV.\n")

    session = Session()
    start = time.time()
    cycle = 0
    stop = False

    def handle_sigint(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_sigint)

    end_time = start + duration_min * 60
    while time.time() < end_time and not stop:
        cycle += 1
        session.record(cycle, start, webview_hint, sidecar_hint)
        last = session.samples[-1]
        print(f"[{last.elapsed_s:>6.1f}s] webview={last.webview_rss_mb} MB  "
              f"sidecar={last.sidecar_rss_mb} MB")
        time.sleep(interval_s)

    out_path = LOG_DIR / f"day44_monitor_{datetime.now():%Y%m%d_%H%M%S}.csv"
    session.write_csv(out_path)
    print(f"\nCSV written: {out_path}")
    session.summarize()


# --- Mode: backend-stress -------------------------------------------------

def run_backend_stress(cycles: int, webview_hint: str, sidecar_hint: str):
    import requests  # local import: only needed for this mode

    files = sorted(REAL_BATCH_DATA.glob("*.nc"))[:5]  # small rotating subset per cycle
    if not files:
        print(f"⚠ No .nc files found under {REAL_BATCH_DATA} — check REAL_BATCH_DATA "
              f"resolution before proceeding (see docstring re: paths.py import).")
        sys.exit(1)

    print(f"Backend-stress mode: {cycles} cycles across {len(files)} rotating files, "
          f"no UI involved (isolates sidecar-side growth).\n")

    session = Session()
    start = time.time()

    for cycle in range(1, cycles + 1):
        f = files[(cycle - 1) % len(files)]
        path_str = str(f)
        try:
            ingest = requests.get(f"{SIDECAR_BASE_URL}/ingest", params={"path": path_str}, timeout=30)
            ingest.raise_for_status()
            meta = ingest.json().get("metadata", {})
            variables = [v for v in meta.get("variables", []) if v != "l2_flags"]
            variable = variables[0] if variables else None
            lat_range = meta.get("lat_range")
            lon_range = meta.get("lon_range")

            if variable and lat_range and lon_range:
                bbox_params = {
                    "path": path_str,
                    "variable": variable,
                    "lat_min": lat_range[0],
                    "lat_max": lat_range[1],
                    "lon_min": lon_range[0],
                    "lon_max": lon_range[1],
                }
                for endpoint in ["/stats", "/raster", "/histogram"]:
                    r = requests.get(f"{SIDECAR_BASE_URL}{endpoint}", params=bbox_params, timeout=30)
                    if r.status_code >= 500:
                        print(f"  ⚠ cycle {cycle} {endpoint} returned {r.status_code}")
        except requests.RequestException as e:
            print(f"  ⚠ cycle {cycle} request failed: {e}")

        session.record(cycle, start, webview_hint, sidecar_hint)
        last = session.samples[-1]
        print(f"[cycle {cycle:>3}] webview={last.webview_rss_mb} MB  "
              f"sidecar={last.sidecar_rss_mb} MB  (file={f.name})")

    out_path = LOG_DIR / f"day44_backend_stress_{datetime.now():%Y%m%d_%H%M%S}.csv"
    session.write_csv(out_path)
    print(f"\nCSV written: {out_path}")
    session.summarize()


# --- Entrypoint --------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Day 44 memory leak detection session")
    parser.add_argument("--mode", choices=["monitor", "backend-stress"], required=True)
    parser.add_argument("--duration-min", type=float, default=30.0,
                         help="monitor mode: total sampling duration")
    parser.add_argument("--interval-s", type=float, default=5.0,
                         help="monitor mode: seconds between samples")
    parser.add_argument("--cycles", type=int, default=30,
                         help="backend-stress mode: number of ingest/query cycles")
    parser.add_argument("--webview-name", default=WEBVIEW_NAME_HINT)
    parser.add_argument("--sidecar-name", default=SIDECAR_NAME_HINT)
    args = parser.parse_args()

    if args.mode == "monitor":
        run_monitor(args.duration_min, args.interval_s, args.webview_name, args.sidecar_name)
    else:
        run_backend_stress(args.cycles, args.webview_name, args.sidecar_name)


if __name__ == "__main__":
    main()