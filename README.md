# OC-ECV Local Engine

**Ocean Color & Essential Climate Variables — Local Engine**

A desktop-hybrid, local-first Earth science application that merges the
browser-based UI/parameter-selection experience of **NASA Giovanni** with
the offline, heavy-processing capabilities of **SeaDAS** — letting users
ingest, process, analyze, and visualize multi-variable spatial-temporal
ocean data entirely on their local machine, with no internet or cloud
dependency required at runtime.

## Status

MVP developed against an original hard deadline of **September 15, 2026**,
extended to **September 17, 2026** by the supervising mentor to
accommodate a requested frontend visual redesign (navy-themed UI, aligned
to a reference desktop application). All core Phase 1-4 functionality
(ingestion, processing/subsetting, visualization, export) was complete and
stable ahead of the original deadline; the redesign and this handover
documentation were the final items addressed before the extended date.

See [`docs/Project_milestone.md`](./docs/Project_milestone.md) for the
full original roadmap and [`docs/`](./docs/) for day-by-day development
history.

## Core Scientific Focus

- **Ocean Color & Biogeochemistry:** Chlorophyll-a, Remote Sensing
  Reflectance, CDOM, POC, TSM/SSC, NFLH
- **Physical Oceanography:** SST, SSH, SSS, Ocean Surface Vector Winds,
  Sea Ice Concentration
- **Energy & Air-Sea Interaction:** PAR, Aerosol Optical Depth

13 ECV categories total; 11 validated against real satellite data spanning
MODIS-Aqua (Ocean Color, SST, IOP), SMAP, CCMP, SWOT, and Sentinel-3 OLCI.

## Architecture

| Layer | Technology |
|---|---|
| Desktop shell | Tauri v2 |
| Frontend | React + TypeScript + Vite |
| Mapping | **MapLibre GL JS + deck.gl** (overlaid mode) — not Leaflet; Leaflet was evaluated and explicitly replaced early in development, see `docs/Day_22_Summary_Report` |
| Bounding-box drawing | terra-draw + terra-draw-maplibre-gl-adapter |
| Charts | Plotly.js (`plotly.js-dist-min`) |
| Backend | Python 3.11 / FastAPI, compiled to a standalone binary via PyInstaller, invoked as a Tauri sidecar over local loopback (`127.0.0.1:5321`) |
| Geospatial processing | xarray, netCDF4, rasterio, GDAL, NumPy |
| Local cache | SQLite |
| Dev environment | Ubuntu / WSL2 (WSLg), conda, Spyder IDE |

The backend runs as a fully self-contained compiled binary — no separate
Python installation is required on the end-user's machine.

## Project Structure

```
oc_ecv_local_engine/
├── frontend/              Tauri + React + Vite app
│   ├── src/
│   │   ├── components/    MapView, ParameterSelector, TimeSeriesPanel,
│   │   │                  HistogramPanel, ScatterPanel, HistoryPanel,
│   │   │                  TopNav, HomePage, AboutPage, HelpPage,
│   │   │                  FileUploader, etc.
│   │   ├── services/      backendApi.ts — typed HTTP client for the sidecar
│   │   ├── utils/         colormaps.ts, etc.
│   │   └── assets/        local images/backgrounds (offline-safe)
│   └── src-tauri/
│       ├── binaries/      compiled Python sidecar binary
│       └── target/release/bundle/appimage/   packaged .AppImage output
├── backend/               Python processing engine (Spyder project root)
│   ├── api/server.py      FastAPI app — all HTTP endpoints
│   ├── ingestion/         file reading (NetCDF/HDF5/HDF4/GeoTIFF)
│   ├── validation/        structural validation, separate from ingestion
│   ├── processing/        subsetting, temporal filtering, quality masking,
│   │                      statistics, raster encoding, parallel utils
│   ├── caching/           SQLite query cache
│   └── requirements-lock.txt
├── shared/                cross-language schemas (frontend ↔ backend contracts)
├── test_data/             gitignored; synthetic + real sample files
└── docs/                  milestone doc, per-day summary reports
```

## Prerequisites

- Ubuntu (native or WSL2 with WSLg) — the only environment this project
  has been built and tested in.
- [Miniconda/Anaconda](https://docs.conda.io/)
- Node.js (LTS) and npm
- Rust toolchain (`rustup`) — required by Tauri
- `xdg-utils` — required for the Tauri AppImage bundler's post-build step

## Local Development Setup

### 1. Python backend environment

> **Note on `requirements-lock.txt`:** this file is a `conda list --export`
> snapshot, not a pip requirements file. Most Python-level packages in it
> are tagged `pypi_0` (pip-installed inside the conda env, not
> conda-installed) — including `xarray`, `fastapi`, `uvicorn`, `pydantic`,
> `pandas`, `earthaccess`, and `pyinstaller`. Running
> `conda create --file requirements-lock.txt` as the file's own header
> comment suggests will likely fail with a `PackagesNotFoundError` on
> those `pypi_0` lines, since that label isn't a real installable conda
> build. Only the genuinely conda-native packages below (gdal, netCDF4,
> rasterio, and their C-library dependencies) can be installed that way.

```bash
cd backend

# GDAL, netCDF4, and rasterio MUST be installed together via conda-forge
# in a single pass -- mixing pip and conda for these three has caused
# shared-library conflicts in the past (see docs/Day_1_Summary_Report).
# Versions pinned to match the original locked environment exactly.
conda create -n oc-ecv-env python=3.11.6
conda activate oc-ecv-env
conda install -c conda-forge \
  gdal=3.6.2 netcdf4=1.6.2 rasterio=1.3.4 \
  hdf4=4.2.15 hdf5=1.12.2 geos=3.11.1 proj=9.1.0 \
  numpy=1.26.4 spyder-kernels=3.1.5

# Remaining Python-level dependencies were pip-installed in the original
# environment (see pypi_0-tagged lines in requirements-lock.txt). Direct
# dependencies pinned explicitly; pip resolves their transitive
# dependencies (aiohttp, botocore, etc. -- earthaccess's own deps) itself.
pip install \
  xarray==2023.1.0 pandas==1.5.3 \
  fastapi==0.139.2 uvicorn==0.51.0 pydantic==2.13.4 \
  pyinstaller==6.21.0 earthaccess==0.17.0 requests==2.34.2 pillow==12.3.0 \
  --break-system-packages
```

> `--break-system-packages` addresses a distro-Python protection that
> doesn't apply inside a conda environment, but is kept for convention;
> harmless here.

Verify:
```bash
python -c "import xarray, netCDF4, rasterio, numpy; print('OK')"
```

### 2. Frontend + dev run

```bash
cd frontend
npm install
npx tsc --noEmit    # type-check before every dev run
npm run tauri dev
```

This launches the desktop window and automatically spawns the Python
sidecar. Verify it's responding:
```bash
curl http://127.0.0.1:5321/health
curl http://127.0.0.1:5321/diagnostics   # confirms GDAL/netCDF4/rasterio import correctly inside the sidecar
```

### 3. Rebuilding the sidecar

**Any change to backend Python source requires a full sidecar rebuild** —
the Tauri app runs the *compiled* binary, not the source directly. A stale
binary silently serving old code has been the single most common class of
bug throughout this project's development.

```bash
cd backend
pkill -f oc-ecv-backend
rm -rf build dist *.spec
pyinstaller --onefile --name oc-ecv-backend \
  --collect-all rasterio --collect-submodules rasterio --collect-all PIL \
  api/server.py
cp dist/oc-ecv-backend ../frontend/src-tauri/binaries/oc-ecv-backend-x86_64-unknown-linux-gnu
chmod +x ../frontend/src-tauri/binaries/oc-ecv-backend-x86_64-unknown-linux-gnu
cd ../frontend && npm run tauri dev
```

### 4. Building the standalone installer

```bash
cd frontend
npm run tauri build
```

Produces a portable `.AppImage` (and `.deb`/`.rpm`, not independently
verified — see Known Limitations) at:
```
frontend/src-tauri/target/release/bundle/appimage/
```

Fully self-contained — no Python, Node, or Rust installation required on
the target machine.

## Supported Data Formats & Scope

| Format | Support level |
|---|---|
| NetCDF (flat-grid and grouped-swath) | Full — ingestion, subsetting, temporal filtering, quality masking, statistics, raster rendering |
| HDF5 (incl. HDF-EOS5 with standard `geophysical_data`/`navigation_data` groups) | Full, same pipeline as NetCDF |
| HDF4 | Ingestion only, confirmed working via the same code path as NetCDF/HDF5. Files using a corner+resolution grid convention (rather than explicit lat/lon coordinates) won't have spatial bounds auto-detected — not encountered in any in-scope ECV product tested to date |
| GeoTIFF | **Ingestion and metadata only** (structure, dimensions, band list, ECV classification, CRS reprojection to lat/lon). Bounding-box query, statistics, temporal filtering, quality masking, and map raster rendering are **not implemented** for GeoTIFF — running a query against a loaded GeoTIFF will fail. Deliberate, documented scope boundary, not a defect |

Variable classification recognizes both NASA OB.DAAC naming (`chlor_a`,
`Rrs_443`) and ESA/Copernicus naming (`CHL_OC4ME`, `TSM_NN`), matched
case-insensitively.

## Known Limitations

- **Sea Ice Concentration** — no standard product successfully acquired via
  `earthaccess`; synthetic test coverage only.
- **TSM/SSC** — no standard downloadable NASA/OB.DAAC product exists;
  typically a regionally-calibrated, third-party-derived product.
  Synthetic coverage only.
- **GeoTIFF query pipeline** and **HDF4 corner+resolution grid bounds** —
  see table above.
- **`/raster` returns HTTP 400** for OSVW (u/v wind components) on very
  large global-scale bounding boxes, while `/stats` succeeds on identical
  parameters — not yet root-caused.
- **Quality flags** are supported by the backend (`/stats` accepts a
  `quality_flags` parameter) but not yet exposed as a UI control.
- **`.deb`/`.rpm` packages** are produced by the Tauri bundler but have not
  been independently installed/verified on a clean system — only the
  `.AppImage` has been verified this way.
- **Bounding-box draw cursor** shows a cosmetic glitch under WSLg/Zink
  software rendering; draw functionality itself is unaffected.
- **Native `<select>` open-dropdown popup list** renders with default OS
  styling rather than the app's navy theme — a WebKitGTK popup-surface
  theming limitation, accepted as known/cosmetic.

### Environment-specific quirks (WSLg / WebKitGTK)

This project has repeatedly hit native OS-level widgets misbehaving
specifically under WSLg's WebKitGTK webview (date pickers, range sliders,
`<select>` background-image styling, an initial-paint flex/grid layout
collapse). The fix each time has been replacing the native widget with a
custom-rendered React/CSS equivalent. If packaging for a native Linux
desktop (outside WSL) or another platform, these workarounds should be
re-evaluated — they may no longer be necessary there.

## Development History

Detailed day-by-day development reports — including every bug found and
fixed, testing methodology, and architectural decisions — are in `docs/`.
Useful for understanding *why* code is structured the way it is, not just
what it does.

## License

TBD