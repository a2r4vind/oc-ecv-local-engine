# Day 2 Summary Report — OC-ECV Local Engine

**Date:** July 22, 2026 (Phase 1, Day 2)
**Phase:** 1 — Environment Setup & Core Ingestion Engine
**Status:** Complete — all exit criteria met

---

## 1. Objective
Configure the Python sidecar process and establish Local Loopback/IPC communication so the Tauri desktop shell can invoke backend processing functions running inside a compiled Python binary.

## 2. Work Completed

**Spyder IDE — Cross-Environment Kernel Setup**
- Discovered `oc-ecv-env` cannot host Spyder directly (GUI stack conflicts with geospatial stack — see Issues below).
- Installed Spyder in a separate environment, kept `oc-ecv-env` GUI-free.
- Installed `spyder-kernels==3.1.x` inside `oc-ecv-env` and pointed Spyder's Python interpreter preference at `~/anaconda3/envs/oc-ecv-env/bin/python`.
- Verified via `sys.executable` and live imports (`xarray`, `netCDF4`, `rasterio`, `numpy` → `1.26.4`) that Spyder now executes code against the correct locked environment while running its own GUI independently.

**FastAPI Sidecar Server**
- Built `backend/api/server.py`: a local-loopback-only FastAPI app (bound to `127.0.0.1`, never `0.0.0.0`) with `/health`, `/version`, and `/diagnostics` endpoints.
- CORS scoped explicitly to Tauri's webview origins (`tauri://localhost`, `https://tauri.localhost`) and the Vite dev server.
- Verified standalone via `python api/server.py` + `curl` before any packaging was attempted.

**PyInstaller Packaging**
- Installed `pyinstaller` via pip (safe alongside conda-managed geospatial packages, since it has no shared-library ABI dependency on them).
- Bundled `server.py` into a single portable binary (`oc-ecv-backend`).
- Added a `/diagnostics` endpoint specifically to verify GDAL/netCDF4/rasterio/xarray actually import inside the frozen binary — caught a real bundling gap this way rather than assuming success from binary size alone.

**Tauri Sidecar Registration**
- Copied the compiled binary into `src-tauri/binaries/` with the required Rust target-triple suffix (`oc-ecv-backend-x86_64-unknown-linux-gnu`, confirmed via `rustc -vV`).
- Registered it under `bundle.externalBin` in `tauri.conf.json`.
- Added `tauri-plugin-shell` and granted a scoped `shell:allow-execute` permission for this specific sidecar binary in `capabilities/default.json`.
- Wired sidecar spawn logic into `src-tauri/src/lib.rs` inside `.setup()`, using `ShellExt`.
- **Confirmed end-to-end:** running `npm run tauri dev` auto-launches the Python sidecar with no manual server start — `curl http://127.0.0.1:5321/health` and `/diagnostics` both responded correctly while only the Tauri app was running.

## 3. Key Issues Resolved

| Issue | Root Cause | Resolution |
|---|---|---|
| `conda install spyder` failed with `LibMambaUnsatisfiableError` | Spyder's Qt/PyQtWebEngine dependency chain requires ICU/PROJ versions that directly conflict with the pinned `libgdal==3.6.2` requirements in the same environment | Installed Spyder in a separate environment; connected it to `oc-ecv-env` via `spyder-kernels`, using Spyder's remote-interpreter feature instead of a shared environment |
| Spyder kernel failed to start (`spyder-kernels version >=3.1.0,<3.2.0` missing) | Spyder's GUI process and the target execution environment need matching kernel protocol versions, and `oc-ecv-env` didn't have the lightweight kernel package installed | `conda install spyder-kernels=3.1` inside `oc-ecv-env` (safe — no GUI/ABI conflict, unlike full Spyder) |
| PyInstaller binary only 26MB — suspiciously small for a GDAL/rasterio/netCDF4 bundle | PyInstaller's static import analysis doesn't detect rasterio's dynamically-loaded Cython submodules (`rasterio.sample`, etc.), silently omitting them | Rebuilt with `--collect-all rasterio --collect-submodules rasterio`; final binary grew to ~148MB and all diagnostics passed |
| `address already in use` on port 5321 during testing | A previous foreground `python api/server.py` process was left running while testing the compiled binary separately | Killed the stale process; adopted a two-terminal workflow (one dedicated to running the server in the foreground, one for `curl` tests) to avoid confusing overlapping output |

**Underlying lesson:** PyInstaller's dependency detection is reliable for straightforward pure-Python packages but frequently misses C-extension packages with dynamic submodule loading (rasterio being the clearest example here). A dedicated `/diagnostics`-style verification endpoint — actually importing and exercising each heavy dependency inside the frozen binary — is essential; binary file size or a generic `/health` check alone is not sufficient proof that bundling succeeded.

## 4. Outcome
- Local Python backend now runs as a fully self-contained, portable sidecar binary — no separate Python install required on any target machine.
- Tauri shell successfully spawns and communicates with this sidecar automatically on app startup via local loopback (`127.0.0.1:5321`).
- All core geospatial dependencies (GDAL, netCDF4, rasterio, xarray) confirmed functional inside the compiled binary, not just the source environment.
- Spyder development workflow fully restored and correctly isolated from the geospatial environment's conflicting GUI dependencies.
- All Phase 1, Day 2 exit-criteria items met; no unresolved blockers carried into Day 3.

## 5. Next Steps (Day 3)
Implement local file ingestion logic using `xarray` and `netCDF4` to parse sample Ocean Color ECV files (Chl-a, Rrs) — the first real use of the ingestion stack now proven functional inside the sidecar.

---
