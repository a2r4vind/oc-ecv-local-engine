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
| `.AppImage` | Functionally verified via full end-to-end regression (packaging, cache persistence, concurrency, all UI tabs, exports) on the Ubuntu 24.04 build machine. **Note:** this verification does not extend to older target systems — see the glibc constraint below, which affects this format equally to the others. |
| `.deb` | Produced as a build artifact. Installs cleanly via `apt` on matching or newer systems; confirmed to fail on Ubuntu 22.04 (see Section 3). |
| `.rpm` | Produced as a build artifact. Not independently install-tested this release (no Red Hat-family test system available), but expected to carry the same glibc constraint as the other two formats, since all three are compiled by the same toolchain on the same build machine. |

**Important correction to prior guidance:** earlier drafts of this document
recommended the `.AppImage` as the "safer" distribution choice relative to
`.deb`/`.rpm` on the basis of verification depth alone. Direct testing has
since shown this framing to be incomplete: **all three formats share an
identical, confirmed glibc 2.39+ requirement** (Section 3) inherited from
the Ubuntu 24.04 build environment, not something specific to one package
type. A target system too old to run the `.deb` is equally unable to run
the `.AppImage` — verification level does not change this. Package format
choice should be based on the target system's actual package management
preference, not on an assumption that AppImage is inherently more portable
in this specific case.

**Recommendation:** confirm the target machine's glibc version (Section 3)
before choosing a distribution format — this is now the primary
deployment gate, ahead of format preference.

---

## 3. System Requirements (Deployment Target)

- Linux x86_64, **glibc ≥ 2.39** (e.g. Ubuntu 24.04 or later)
- No Python, Node.js, or other runtime installation required on the target machine — the backend is a fully self-contained compiled binary bundled inside the AppImage
- Recommended: 4GB+ RAM, especially for large multi-gigabyte NetCDF files or heavy multi-tab usage

**glibc requirement — confirmed, not assumed:** all three package formats
are built on Ubuntu 24.04 and dynamically link against its glibc/GTK/
WebKitGTK stack at build time. Direct testing on an Ubuntu 22.04 machine
(glibc 2.35) produced launch failures for both the `.deb` and the
`.AppImage`, with errors of the form:
```
oc-ecv-local_engine: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.39' not found (required by oc-ecv-local_engine)
```
and, for the AppImage specifically, cascading identical errors against
nearly every bundled GTK/WebKitGTK library (`libgdk`, `libcairo`,
`libwebkit2gtk`, `libglib`, and others) — confirming the constraint is
systemic to the build environment, not a single missing dependency.
`--appimage-extract-and-run` and other extraction flags do not work
around this; glibc is intentionally excluded from AppImage bundling as a
base-OS-level dependency.

**To check a target machine's glibc version before deployment:**
```bash
ldd --version
```

**Remediation path (not performed this release):** producing artifacts
compatible with older distributions requires compiling the full toolchain
(Tauri build + PyInstaller sidecar) on an equivalently older base system,
e.g. Ubuntu 22.04, and re-running the full verification pass described in
Section 7. This is a non-trivial rebuild, not a configuration change, and
is out of scope for the current MVP release.

---

## 4. Installation

```bash
chmod +x oc-ecv-local_engine_0.1.0_amd64.AppImage
./oc-ecv-local_engine_0.1.0_amd64.AppImage
```

No further setup is required, provided the target system meets the glibc
requirement in Section 3. The bundled Python backend extracts to a
temporary, randomized mount path on each launch (`/tmp/.mount_XXXXXXX/...`,
standard AppImage behavior) and is torn down cleanly on exit.

For `.deb` installation, prefer `apt` over raw `dpkg -i` so missing
runtime dependencies (e.g. `libwebkit2gtk-4.1-0`) are resolved
automatically:
```bash
sudo apt install ./oc-ecv-local_engine_0.1.0_amd64.deb
```

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
5. **Note added this release:** the build machine's own OS/glibc version is itself part of what must be verified against — a clean build and a clean install-and-launch on the build machine does not confirm behavior on any other target system's OS version (see Section 3).

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
| 8 | **All packaged formats require glibc ≥ 2.39** (e.g. Ubuntu 24.04+) on the target machine | **Confirmed via direct testing** on Ubuntu 22.04 (glibc 2.35): both `.deb` and `.AppImage` fail to launch with `GLIBC_2.38`/`GLIBC_2.39 not found` errors. This affects all three formats equally — see Sections 2 and 3. No workaround exists short of rebuilding the full toolchain on an older base system (out of scope this release). Supersedes the previous framing of `.deb`/`.rpm` as merely "less verified" than `.AppImage`; the real constraint is the build machine's glibc version, not format choice. |
| 9 | `npm audit` reports 3 critical severity findings (frontend dependencies) | All three collapse to one advisory (GHSA-jrc7-96c5-q579, a MapLibre GL JS XSS sanitizer bypass), reachable via `maplibre-gl` directly and via a bundled copy inside `plotly.js`/`react-plotly.js`. Investigated directly via source review: the vulnerable API surface (`Popup.setHTML()`/`setText()`, HTML-content `Marker`s) is never invoked anywhere in this codebase's map or chart components. Confirmed non-exploitable given actual usage; not remediated via `npm audit fix --force` since that would force a breaking `plotly.js` upgrade for no reduction in real risk. |

---

## 9. Support Checklist

When investigating a reported issue, gather in order:

1. **Confirm the target machine's glibc version** (`ldd --version`) if the report is "the app won't launch at all" rather than a functional/data issue — this is now the first thing to rule out, given the confirmed glibc ≥ 2.39 requirement (Section 3). A launch failure on a system below this version is expected behavior, not a new bug.
2. **`/diagnostics` output** — confirms the sidecar's bundled dependencies are intact (only reachable once the app successfully launches).
3. **Whether the issue reproduces on a fresh cache** — relaunch with `OC_ECV_DATA_DIR` pointed at an empty temp directory (Section 5) to rule out a stale/corrupted cache entry.
4. **The exact file, variable, bounding box, and date range** used, plus whether the source file is a single-pass swath product or a multi-time-step gridded product — many "no data" reports trace back to genuinely sparse valid data (cloud cover, sun glint) in a specific real-world pass rather than an application defect.
5. **Whether the issue reproduces after a full application restart** — some classes of bugs in this project have historically only manifested across restarts, not within a single session.