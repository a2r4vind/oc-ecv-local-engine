# Day 38 Summary Report — OC-ECV Local Engine

**Date:** August 27, 2026 (Phase 4, Day 38)
**Phase:** 4 — Export Engines & Advanced Utilities
**Status:** Complete — georeferenced raster export (.tif / .nc) implemented for both flat-grid and swath file structures; verified at source, compiled-sidecar, and live-UI levels; zero regressions to existing export paths

## 1. Objective
Implement georeferenced raster export (.tif / GeoTIFF or NetCDF subset export), per the milestone's Phase 4 Day 38 item — extending Day 37's raw numeric export into a GIS-interoperable spatial format, ahead of Day 40-42's external GIS validation window.

## 2. Design Decision: Format Fork by File Structure, Not User Choice
Unlike Day 37's CSV/.bin (a genuine user choice applying to either structure), georeferenced export required resolving a real fork before writing code:
- **Flat-grid → GeoTIFF.** Regular 1D lat/lon grid maps directly onto GeoTIFF's affine-transform model. Straightforward, standard, EPSG:4326.
- **Swath → CF-1.8 NetCDF, not a regridded GeoTIFF.** Real MODIS/SWOT-style swath data has 2D per-pixel, non-rectilinear lat/lon (satellite ground-track geometry) with no native GeoTIFF representation. Forcing it into GeoTIFF would require resampling onto a regular grid — silently inventing pixel values between real ground-track samples. Consistent with this project's established refusal to introduce unverified approximation into scientific data (Day 20's valid_min/max bug, Day 8/10/11's verify-before-trusting pattern), swath is exported as CF-1.8 NetCDF instead, preserving native per-pixel geometry with zero interpolation. This decision was made explicit and confirmed with AKV before implementation, rather than picked silently.

Format is therefore not a query parameter on `/export-geo` — the backend determines it from `structure_type` and reports which one it produced via a new `X-Export-Kind` response header.

## 3. Pre-Implementation Verification (before writing the real module)
Both write paths were verified independently before being wired into any endpoint, given this project's established standard that library *write* support cannot be assumed just because *read* support is proven (Day 2's PyInstaller submodule-detection gap was exactly this class of gap, for reading):
- `rasterio` GeoTIFF write/readback verified in source (`verify_day38_geotiff_writer.py`) — CRS, bounds, and NaN-as-nodata all round-tripped correctly.
- `xarray.to_netcdf()` CF-swath structure verified in source (`verify_day38_netcdf_writer.py`) — 2D `lat`/`lon` coordinate variables, `crs` grid-mapping variable, `Conventions: CF-1.8` all present as designed.
- Both formats cross-checked via `gdalinfo` independently of QGIS (QGIS not installed locally) — confirmed GDAL's own driver recognizes the swath NetCDF as a genuine **geolocation-array dataset** (`Geolocation:` block with `X_DATASET`/`Y_DATASET` pointing at `lon`/`lat` subdatasets), not an opaque blob — the key signal that real GIS tooling can georeference it without a companion regridding step.
- **Sidecar write-mode verified separately from source**, via a temporary diagnostic block added to `/diagnostics`, rebuilt into the compiled binary, and curl-checked (`geotiff_write_check.ok: true`, `netcdf_swath_write_check.ok: true`) before any real endpoint code was written — consistent with Day 16/18's standard that concurrency/binary-specific behavior must be checked against the actual frozen artifact, not assumed from source-level success. Temporary block removed after verification.

## 4. Work Completed

**New Module (`backend/processing/geo_export.py`)**
- `encode_geotiff()` — single-band float32 GeoTIFF, EPSG:4326, NaN-as-nodata, north-up orientation matching `raster.py`'s and `raw_export.py`'s established row-ordering convention. Writes to a real temp file and reads bytes back (`rasterio` has no clean in-memory GTiff write API in the pinned version), verified working in both source and sidecar before being relied on.
- `encode_netcdf_swath()` — CF-1.8 NetCDF with native 2D per-pixel `lat`/`lon` coordinates (no regridding), dummy `crs` grid-mapping variable, `Conventions`/`title` global attributes. Same temp-file-then-read-bytes pattern as the GeoTIFF path.
- `compute_raw_export()`-equivalent `compute_geo_export()` — reuses `_get_subsetted_data()` exactly as `raster.py` (Day 23) and `raw_export.py` (Day 37) do; dispatches to the correct encoder based on `structure_type`; returns `(payload, media_type, export_kind)`.

**Backend (`server.py`)**
- New `/export-geo` endpoint — same query parameters as `/stats`/`/raster`/`/export-raw`, no `format` param (not a caller choice here). Catches `GeoExportError` alongside existing error types, returns 400 not 500.
- Added `X-Export-Kind` to `expose_headers` in CORS middleware — same proactive fix Day 23 applied for `/raster`'s custom headers, avoiding a repeat of that "headers silently null" gotcha.

**Frontend**
- `services/backendApi.ts`: `fetchGeoExport()` — same `StatsQuery` shape as the other export fetchers, returns `{ blob, exportKind }` so the caller can pick the correct file extension from the server's own determination rather than guessing client-side.
- `utils/geoExport.ts` (new): `exportGeoData()` — mirrors Day 37's `exportRawData()` exactly, reuses Day 36's `saveFile.ts` unchanged.
- `components/GeoExportButton/GeoExportButton.tsx` (new): single-button component, no format selector (deliberately kept separate from `RawExportButton` rather than merged, since the two have genuinely different shapes — one is a user choice, one isn't). Reuses `ExportButton.css`.
- `App.tsx`: `GeoExportButton` rendered alongside `RawExportButton` in the existing Query-tab `map-controls` block, gated on the same `lastQuery` state Day 37 introduced — no new state needed, since both exports target the identical last-run query.

## 5. Issues Found and Fixed

| # | Issue | Root Cause | Resolution |
|---|---|---|---|
| 1 | First `/export-geo` curl attempts returned a 22-byte body (`{"detail":"Not Found"}`) despite the endpoint appearing correctly in `server.py` source | Classic Day 5 recurrence: the running sidecar was still the pre-Day-38 compiled binary — editing `server.py` source doesn't change what an already-running frozen process executes | Rebuilt and restarted the sidecar via the standard routine; re-confirmed via source-level direct call first (isolating "is the module correct" from "is the binary stale") before re-curling |
| 2 | `ModuleNotFoundError: No module named 'processing.geo_export'` on first source-level check | The module code had been reviewed/discussed but never actually saved to disk at `backend/processing/geo_export.py` before the rebuild was attempted | Created the actual file; re-verified source-level import and a direct `compute_geo_export()` call before rebuilding again |

Both were process/sequencing slips (stale artifact, un-saved file), not logic bugs — caught immediately by the project's established "verify source before rebuilding, verify rebuild before trusting" discipline rather than propagating into a confusing downstream failure.

## 6. Testing Summary

**Backend curl verification (compiled sidecar, real + synthetic data):**

| # | Test | Result |
|---|---|---|
| 1 | GeoTIFF export — flat-grid (`sample_oceancolor.nc`, bbox `[33,36,-124,-120]`, `chlor_a`) | ✅ `40×30` grid, correct CRS/bounds snapped to actual grid cells, `VARIABLE=chlor_a` tag, `NoData=nan` |
| 2 | NetCDF export — real MODIS swath (`AQUA_MODIS...L2.OC.nc`, bbox `[8,16,82,90]`, `chlor_a`) | ✅ `988×798` array; GDAL recognized full geolocation-array structure (`X_DATASET`/`Y_DATASET`, resolved WGS84 SRS), `Conventions=CF-1.8` |
| 3 | Non-overlapping bbox | ✅ Clean HTTP 400, `"Bounding box [...] does not overlap this file"` — same error path/message convention as `/stats` |

**Frontend/live-UI verification (both buttons, both file structures, three separate real exports):**

| # | Test | Result |
|---|---|---|
| 1 | `npx tsc --noEmit` before any runtime testing | ✅ Clean — no repeat of Day 37's compile-time issues |
| 2 | Run Query on flat-grid file → Export → save dialog offers `.tif` filter → saved file has `.tif` extension | ✅ |
| 3 | `gdalinfo` on the app-exported `.tif` | ✅ Matches curl-verified structure exactly (CRS, bounds, variable tag) |
| 4 | Switch to real MODIS file, query `aot_869` → Export → `.nc` | ✅ Correct geolocation-array recognition, correct variable name in metadata |
| 5 | Same file, query `sst` → Export → `.nc` | ✅ Second independent variable confirms the swath path isn't accidentally hardcoded to one variable name |
| 6 | `RawExportButton` (Day 37) regression check alongside new `GeoExportButton` | ✅ Unaffected |

## 7. Outcome
- Georeferenced export (.tif for flat-grid, CF-1.8 NetCDF for swath) is fully implemented, verified at three independent levels (source, compiled sidecar, live UI), and tested against real satellite data across two file structures and three distinct variables (`chlor_a`, `aot_869`, `sst`).
- The flat-grid/swath format fork was resolved deliberately (NetCDF over regridded-GeoTIFF for swath) before implementation, avoiding any interpolation/approximation in the exported science data — consistent with this project's established principle.
- Sidecar write-mode support for both `rasterio` (GeoTIFF) and `xarray` (NetCDF) was verified as a genuinely separate concern from read-mode support, closing a class of risk this project hadn't previously tested (write, not read, inside the frozen binary).
- `/raster`, `/export-raw`, and all other existing endpoints remain untouched — zero regression risk, confirmed via direct `RawExportButton` regression check.
- One known follow-up, not a defect: GDAL reports the swath NetCDF's `Corner Coordinates` in pixel/line space, not geographic degrees, since it's a geolocation-array dataset — some GIS tools may need an explicit `-geoloc` resample step or manual layering of the `lat`/`lon` subdatasets. Flagged specifically for Day 40-42's QGIS validation window, not resolved here.
- Minor unrelated observation logged, not investigated: `/diagnostics` reports `xarray` version as the literal string `"999"` inside the compiled sidecar — likely a `pkg_resources` version-resolution quirk specific to the frozen build. Does not affect functionality; worth a 10-minute look during a future buffer window.
- All Phase 4, Day 38 exit-criteria items met: users can export GIS-interoperable spatial files, format automatically matched to the data's actual geometry rather than approximated.

## 8. Next Steps (Day 39, with a prerequisite)
Day 39's milestone item is the processing history panel, built on Day 18's `query_cache` SQLite table. Per the carried-forward issue tracked since Day 19-21 ("query cache silently serving pre-fix results after logic changes — no code-version awareness in cache key"), **cache-key versioning must be fixed before Day 39 begins**, not alongside it — building a history panel on top of a cache with a known staleness bug would surface confusing, hard-to-trace symptoms in the very feature meant to make past queries trustworthy and reviewable.