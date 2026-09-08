# OC-ECV Local Engine — Administrator & Deployment Guide

**Version:** 0.1.0 (MVP)
**Last updated:** September 2026
**Repository:** a2r4vind/oc-ecv-local-engine

---

## 1. Architecture Overview

OC-ECV Local Engine is a local-first desktop application with two components packaged into a single distributable:

- **Frontend:** Tauri v2 + React + TypeScript + Vite. Renders the UI, map (MapLibre GL JS + deck.gl), and charts (Plotly.js).
- **Backend:** A Python/FastAPI application, compiled via PyInstaller into a standalone binary ("sidecar"), spawned automatically by the Tauri shell on launch and communicating over local loopback only (`127.0.0.1:5321`). The backend is never exposed on any network-reachable interface.

The two communicate entirely over `localhost` HTTP; no external network access is required or used at runtime.

---

## 2. Distribution Formats

The build produces three Linux package formats from a single `tauri build` invocation:

| Format | Status |
|---|---|
| `.AppImage` | **Primary, fully verified distribution format.** Portable, no installation required. This release's complete end-to-end regression (packaging, cache persistence, concurrency, all UI tabs, exports) was performed against this format specifically. |
| `.deb` | Produced as a build artifact. Has not been through the same dedicated verification pass as the AppImage this release — treat as unverified/best-effort if distributing via this channel. |
| `.rpm` | Same status as `.deb` — produced, not independently verified this release. |

**Recommendation:** distribute the `.AppImage` as the primary supported artifact until `.deb`/`.rpm` receive their own dedicated verification pass.

---

## 3. System Requirements (Deployment Target)

- Linux x86_64 (tested: Ubuntu 24.04, WSL2/Ubuntu)
- No Python, Node.js, or other runtime installation required on the target machine — the backend is a fully self-contained compiled binary bundled inside the AppImage
- Recommended: 4GB+ RAM, especially for large multi-gigabyte NetCDF files or heavy multi-tab usage

---

## 4. Installation

```bash
chmod +x oc-ecv-local_engine_0.1.0_amd64.AppImage
./oc-ecv-local_engine_0.1.0_amd64.AppImage
```

No further setup is required. The bundled Python backend extracts to a temporary, randomized mount path on each launch (`/tmp/.mount_XXXXXXX/...`, standard AppImage behavior) and is torn down cleanly on exit.

---

## 5. Data & Cache Storage

The application persists a local SQLite query cache to avoid redundant recomputation on repeated identical queries.

**Location (default):**
```
$XDG_DATA_HOME/oc-ecv-local-engine/cache/query_cache.db
```
falling back to:
```
~/.local/share/oc-ecv-local-engine/cache/query_cache.db
```
if `XDG_DATA_HOME` is not set.

This is an OS-standard, per-user, writable location — chosen specifically because neither the AppImage's own randomized mount path nor the PyInstaller bootloader's temporary extraction directory is a valid persistent-storage location (both are ephemeral and/or read-only). The cache correctly survives full application restarts and reinstalls, since it lives outside the application bundle entirely.

### `OC_ECV_DATA_DIR` — Support & Troubleshooting Override

Setting the `OC_ECV_DATA_DIR` environment variable before launch overrides the cache location entirely:

```bash
OC_ECV_DATA_DIR=/path/to/custom/location ./oc-ecv-local_engine_0.1.0_amd64.AppImage
```

**When this is useful:**
- **Diagnosing cache-related issues** — point at a fresh empty directory to rule out a corrupted or stale cache without deleting the user's real cache.
- **Restricted or non-standard home directories** — shared/managed machines where `~/.local/share` may not be writable or may not exist.
- **Multiple isolated test instances** — QA or support reproduction scenarios needing a clean, disposable cache per run.

The cache database itself is a standard SQLite file (`query_cache` table: file path, variable, bounding box, date range, quality flags, result JSON, hit count, and timestamp) and can be inspected directly with any SQLite client if deeper diagnosis is needed. It can also be safely deleted at any time — the application will recreate it automatically, at the cost of recomputing previously-cached queries.

---

## 6. Backend Endpoints (Reference)

All endpoints are served on `127.0.0.1:5321` and are not reachable from outside the local machine.

| Endpoint | Purpose |
|---|---|
| `/health` | Basic liveness check |
| `/version` | Backend version info |
| `/diagnostics` | Confirms core dependencies (GDAL, netCDF4, rasterio, xarray, Pillow) are correctly bundled and importable — useful first check if the app appears to load but queries fail |
| `/ingest` | Parses an uploaded file's metadata |
| `/stats` | Computes regional statistics for a variable/bbox/date query (cached) |
| `/raster` | Returns a rendered raster (PNG) or point-data payload for map display |
| `/timeseries-within-file` | Time series for multi-time-step files |
| `/histogram` | Histogram data for a variable/region |
| `/scatter` | Two-variable correlation data for a region |
| `/stats-multi` | Multi-variable statistics in one call |
| `/batch-timeseries` | Time series aggregated across a directory of files |
| `/batch-date-coverage` | Date coverage summary across a directory |
| `/export-raw` | CSV/raw data export |
| `/export-geo` | GeoTIFF/NetCDF export |
| `/history` | Read-only browse of the query cache (powers the History tab) |

---

## 7. Rebuilding the Sidecar (Developers Only)

Any change to the Python backend requires rebuilding the compiled sidecar binary before it takes effect — the running application uses the compiled artifact, not the source files, and stale binaries are a known, previously-encountered failure mode in this project.

```bash
cd backend
pkill -f oc-ecv-backend
rm -rf build dist *.spec
pyinstaller --onefile --name oc-ecv-backend --collect-all rasterio \
  --collect-submodules rasterio --collect-all PIL api/server.py
cp dist/oc-ecv-backend ../frontend/src-tauri/binaries/oc-ecv-backend-x86_64-unknown-linux-gnu
chmod +x ../frontend/src-tauri/binaries/oc-ecv-backend-x86_64-unknown-linux-gnu
```

Then rebuild the AppImage:

```bash
cd frontend
npm run tauri build
```

**Verification standard for any sidecar change touching paths, caching, lifecycle, or concurrency** (established through direct experience on this project — a single clean test pass has previously missed real bugs, including a race condition and two separate cache-path failures):

1. Verify against the compiled binary directly (not just source), via its `/diagnostics` and relevant endpoints.
2. Verify again against the actual packaged AppImage output — packaged-path behavior has previously differed from both source and raw-compiled-binary behavior.
3. Verify across a **full application restart**, not just repeated calls within one running session — some failure modes only appear across restarts.
4. Run **repeated trials (10-20+)**, not a single pass, for anything concurrency- or timing-sensitive.

---

## 8. Known Issues & Limitations

| # | Issue | Status |
|---|---|---|
| 1 | Sidecar process crash under rapid repeated queries | Monitored; no reproduction in recent stress testing since a stdout/stderr piping fix. Watch for recurrence. |
| 2 | `/raster` returns HTTP 400 for Ocean Surface Vector Wind (u/v) variables on very large, global-scale bounding boxes, while `/stats` succeeds on identical parameters | Reproduced, not yet root-caused at the source level. Workaround: use smaller/regional bounding boxes for OSVW raster display. |
| 3 | Sea Ice Concentration ECV | Deferred post-MVP — no working NASA data access path found via `earthaccess`/CMR after multiple attempts; likely requires direct NSIDC tooling. Synthetic test coverage only. |
| 4 | Total Suspended Matter / Suspended Sediment Concentration ECV | Deferred — confirmed no standard downloadable NASA/OB.DAAC product exists; this is typically a regionally-calibrated third-party product. Synthetic test coverage only. |
| 5 | Quality flag (cloud/land/glint) filtering | Backend fully supports this; not yet exposed in the parameter-selection UI. |
| 6 | Bounding-box draw tool cursor doesn't visually change to a crosshair | Cosmetic only (known Linux/WebKitGTK software-rendering rendering quirk under certain graphics configurations); draw functionality itself is unaffected. |
| 7 | `scattergl` (WebGL scatter plot) trace recreates its rendering context on every new scatter query | Confirmed intrinsic to the Plotly.js/regl library, not a bug in this application's code. Under software-rendered graphics environments, this can contribute to memory growth under heavy sustained scatter-tab usage (15+ consecutive queries). Application remains functional throughout; no crashes observed in testing. |
| 8 | `.deb` / `.rpm` packages | Produced by the build but not independently verified this release (see Section 2) |

---

## 9. Support Checklist

When investigating a reported issue, gather in order:

1. **`/diagnostics` output** — confirms the sidecar's bundled dependencies are intact.
2. **Whether the issue reproduces on a fresh cache** — relaunch with `OC_ECV_DATA_DIR` pointed at an empty temp directory (Section 5) to rule out a stale/corrupted cache entry.
3. **The exact file, variable, bounding box, and date range** used, plus whether the source file is a single-pass swath product or a multi-time-step gridded product — many "no data" reports trace back to genuinely sparse valid data (cloud cover, sun glint) in a specific real-world pass rather than an application defect.
4. **Whether the issue reproduces after a full application restart** — some classes of bugs in this project have historically only manifested across restarts, not within a single session.