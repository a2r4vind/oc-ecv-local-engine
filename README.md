# OC-ECV Local Engine

**Ocean Color & Essential Climate Variables Local Engine**

A desktop-hybrid, local-first Earth science application that merges the
browser-based UI/parameter-selection experience of **NASA Giovanni** with the
offline, heavy-processing capabilities of **SeaDAS** — letting users ingest,
process, analyze, and visualize multi-variable spatial-temporal ocean data
entirely on their local machine, with no internet or cloud dependency required.

## Status

🚧 Active development — MVP target: **September 15, 2026**

Currently in **Phase 1: Environment Setup & Core Ingestion Engine** (Week 1 of 8).
See [`Project_milestone.md`](./docs/Project_milestone.md) for the full roadmap.

## Core Scientific Focus

- **Ocean Color & Biogeochemistry:** Chlorophyll-a, Remote Sensing Reflectance,
  CDOM, POC, TSM/SSC, NFLH
- **Physical Oceanography:** SST, SSH, SSS, Ocean Surface Vector Winds,
  Sea Ice Concentration
- **Energy & Air-Sea Interaction:** PAR, Aerosol Optical Depth

## Architecture

- **Desktop Shell:** Tauri v2
- **Frontend:** React + TypeScript + Vite, with Leaflet/Deck.gl for mapping
- **Processing Backend:** Python (xarray, netCDF4, rasterio, GDAL), packaged
  as a standalone PyInstaller binary and invoked as a Tauri sidecar over
  local loopback (FastAPI + Uvicorn on `127.0.0.1:5321`)

## Project Structure

oc_ecv_local_engine/
├── frontend/ # Tauri + React desktop shell
│ ├── src/
│ └── src-tauri/
├── backend/ # Python processing engine (Spyder project root)
│ ├── ingestion/
│ ├── processing/
│ ├── validation/
│ ├── api/
│ └── requirements-lock.txt
├── shared/ # Cross-language schemas (frontend ↔ backend contracts)
└── docs/ # Milestone docs, daily summary reports

## Local Development Setup

**Prerequisites:** Rust toolchain, Node.js (LTS), Anaconda/Miniconda

```bash
# Backend environment
conda create -n oc-ecv-env python=3.11.15
conda activate oc-ecv-env
conda install -c conda-forge gdal=3.6.2 netcdf4=1.6.2 rasterio=1.3.4 -y
pip install fastapi uvicorn

# Frontend
cd frontend
npm install
npm run tauri dev
```

## License

TBD
