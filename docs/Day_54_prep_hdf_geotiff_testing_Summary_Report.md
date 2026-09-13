# Day 54 Summary Report — OC-ECV Local Engine

Date: September 13, 2026 (Pre-Day 54, Handover Prep)
Phase: 5 — Comprehensive Testing, Packaging & Deployment (Days 54-56 prep)
Status: ✅ Complete — genuine format-coverage gap identified and substantially closed ahead of Days 54-56; scope deliberately bounded given the September 17 deadline

## 1. Objective
Before starting Day 54 (README) and the Day 56 exit-criteria check, verify the app's actual behavior against HDF and GeoTIFF files — both named explicitly in Phase 1's original exit criteria ("Local NetCDF/GeoTIFF files can be selected via UI and successfully parsed") and the project summary's core ingestion scope ("NetCDF, HDF, GeoTIFF") — since every prior day's testing (Days 1-25, all real-data validation through Day 21) exercised NetCDF/HDF5 files exclusively. This gap was not previously flagged in any day report and was caught only by direct pre-handover review of the milestone doc against actual test coverage.

## 2. Scoping Decision
Given ~4 days remaining to the September 17 deadline and Days 54-56 not yet started, testing was deliberately scoped to a **quick smoke test**: confirm the ingestion pipeline doesn't crash and produces sane output against one real file per format, fix only cheap/high-value bugs found along the way, and explicitly defer anything requiring multi-day integration work. Full query/subsetting/statistics/raster-rendering parity with NetCDF (already achieved across 13 ECV categories and 5 real missions through Day 21) was ruled out of scope from the outset for both formats.

## 3. HDF Testing

**Test file:** `MYD14CM1.201512.005.01.hdf` — real MODIS Thermal Anomalies/Fire monthly L3 CMG product, classic **HDF4** format (not HDF5/HDF-EOS5).

**Result: ingestion succeeded with no code changes.** The existing `xr.open_dataset(engine="netcdf4")` call correctly opened the file, extracted global attributes, dimensions (`360×180`, global 1° grid), and all four variables (`CorrFirePix`, `CloudCorrFirePix`, `MeanPower`, `MeanCloudFraction`). This conda-forge `netCDF4` build evidently supports HDF4 transparently — no dedicated HDF4 driver work was needed, contrary to initial expectation going into this test.

**Genuine gap found (not fixed — see rationale):** `MISSING_LAT_RANGE`/`MISSING_LON_RANGE` validation errors. This file encodes spatial extent via a corner-plus-resolution convention (`"UL corner": "[-180. 90.]"`, `"resolution": "1 degree"`, plus grid dimensions) rather than explicit lat/lon coordinate arrays or `geospatial_lat/lon_min/max` global attributes — the only two conventions `extract_metadata()` currently checks. This is a real, previously untested third convention.

`NO_ECV_VARIABLES` was also raised, correctly — this is a Fire/Thermal Anomalies product, genuinely outside this project's Ocean Color/ECV scope; none of its four variables should match any ECV category.

**Decision: documented as a known limitation, not fixed.** This specific file (and its product family) will never be usable in this app regardless of bounds detection, since it contains no in-scope ECV variables. No ECV product tested to date (13 categories, 5 real missions) has exhibited this convention. Effort was not spent here.

## 4. GeoTIFF Testing

**Starting state:** GeoTIFF had **zero implementation**. `open_dataset()` was hardcoded to `xr.open_dataset(path, engine="netcdf4", ...)` — pointing it at a `.tif` file threw an exception immediately. `rasterio` has been an installed dependency since Day 1 but had never been wired into the ingestion path. This reframed "GeoTIFF testing" from a test into a first-implementation task.

**Effort estimate produced before implementation** (per this project's established discipline of sizing work before committing to it):
- **Tier 1 (ingestion + metadata only):** ~1-2 hours — matches the literal Day 1 exit-criteria wording.
- **Tier 2 (full subsetting/stats/quality-mask/raster-rendering parity with NetCDF):** multi-day — every downstream module (`subsetting.py`, `statistics.py`, `raster.py`) assumes an `xarray.Dataset` with NetCDF-style variables/coords; extending that to GeoTIFF's raster/band model is comparable in scope to Days 21-22's real file-structure integrations, each of which took a full day and surfaced multiple bugs.

**Decision:** implement Tier 1 only; formally defer Tier 2, same treatment already established for Sea Ice Concentration and TSM/SSC.

### 4.1 Tier 1 Implementation (`backend/ingestion/netcdf_reader.py`)
- `_is_geotiff()` — extension-based dispatch (`.tif`/`.tiff`).
- `extract_metadata_geotiff()` — opens via `rasterio` directly (no new dependency), extracts width/height/band count/CRS/bounds/dtype, and **reprojects bounds to EPSG:4326 via `rasterio.warp.transform_bounds`** when the source CRS differs — anticipating that most real-world GeoTIFFs are not natively lat/lon.
- `identify_ecv_variables_geotiff()` — classifies bands by description first, falling back to filename matching when bands carry no description (common for analytical exports, confirmed below) rather than leaving a classifiable file with zero classified ECVs.
- Dispatch added to `extract_metadata()` and `identify_ecv_variables()`; `parse_file()` required no changes, since both functions now self-dispatch.

### 4.2 Real-File Acquisition
No real GeoTIFF was on hand. Rather than default to a synthetic fixture, a real file was deliberately sourced: **Sentinel-3 OLCI Level-2 WFR** chlorophyll data via the **Copernicus Data Space Browser**, using its "Analytical" export mode (TIFF, 32-bit float, raw `CHL_OC4ME` band) rather than the raw SAFE product download (which is NetCDF-only and was initially downloaded in error before the distinction was clarified). The resulting export happened to be in **UTM Zone 43N (EPSG:32643)**, not EPSG:4326 — giving a genuine, unplanned real-world test of the reprojection branch rather than a synthetic best-case.

### 4.3 Bugs Found and Fixed

| # | Bug | Root Cause | Resolution |
|---|---|---|---|
| 1 | GeoTIFF had no ingestion path at all | `open_dataset()` hardcoded to `engine="netcdf4"`; `rasterio` installed since Day 1 but never wired in | Added dedicated `rasterio`-based Tier 1 path (metadata/ingestion only, per scope decision above) |
| 2 | Real Sentinel-3 export classified as `NO_ECV_VARIABLES` despite being a genuine chlorophyll product | Band carried no description (`band_1`), and `KNOWN_ECV_PREFIXES` only recognized NASA OB.DAAC naming (`chlor_a`, `chl_ocx`, `chl_a`) — first non-NASA data provider tested in this project, using ESA/Copernicus naming (`CHL_OC4ME`) | Added ESA/Copernicus naming variants (`chl_oc4me`, `chl_nn`, `a865`, `t865`, etc.) to `KNOWN_ECV_PREFIXES`, sourced from the actual OLCI L2 Water layer list |
| 3 | Even after adding ESA variant strings, matching remained fragile to case | `identify_ecv_variables()`/`identify_ecv_variables_geotiff()` used case-sensitive `str.startswith()`; NASA convention is lowercase, ESA/Copernicus is uppercase | Normalized both the discovered variable name and each known prefix to lowercase before comparison in both the NetCDF/HDF and GeoTIFF classification functions — closes the whole class of cross-provider case mismatch, not just this one instance |

### 4.4 Verification
Re-ran `python ingestion/netcdf_reader.py` against the real Sentinel-3 file after the fix (source-level only — **sidecar rebuild deliberately deferred**, see Section 5):
- `structure: "geotiff_raster"` ✅
- `source_crs: "EPSG:32643"` correctly reprojected to `lat_range: [5.29, 26.16]`, `lon_range: [60.42, 95.74]` — plausible Arabian Sea/Bay of Bengal coverage matching the queried AOI ✅
- `ecv_variables.chlorophyll: ["band_1"]` via filename fallback ✅
- `validation.valid: true`, only the expected `NO_TIME_INFO` warning (correct — static analytical exports carry no time dimension, same category as single-granule swath files) ✅

## 5. Deliberately Out of Scope This Session
- **GUI/sidecar testing.** All testing above was source-level (`python ingestion/netcdf_reader.py <file>`) only. The compiled PyInstaller sidecar has **not** been rebuilt with today's changes and does not yet reflect them.
- **Query/stats/raster pipeline for GeoTIFF.** `compute_regional_stats()`/`_get_subsetted_data()` still only dispatch on `flat_grid`/`grouped_swath` and open files via the NetCDF-only engine. A GeoTIFF file loaded through the UI today would display correct ingestion metadata but **fail on "Run Query"** — a known, deliberate Tier 2 scope boundary (documented inline in `netcdf_reader.py`), not a regression.
- **HDF4 corner+resolution grid bounds parsing** — documented limitation per Section 3, not fixed.
- **File-picker dialog compatibility** for `.tif`/`.tiff` extensions in `FileUploader.tsx` — not yet verified; needs a source review before any GUI test is attempted.

## 6. Outcome
- Closed a real, previously undetected coverage gap between original Phase 1/project-summary scope (NetCDF, HDF, GeoTIFF) and actual test history (NetCDF/HDF5 only through Day 25).
- HDF4 confirmed working via the existing pipeline with no code changes required.
- GeoTIFF Tier 1 (ingestion + metadata) implemented, verified against a real, non-trivial file (real provider, real UTM CRS, real classification gap), and hardened against the same cross-provider naming-convention risk that HDF/GeoTIFF testing was specifically designed to surface.
- One structural limitation (HDF4 corner+resolution grids) and one deliberate scope boundary (GeoTIFF Tier 2) formally documented rather than silently left unaddressed — consistent with this project's established practice of honest deferral over silent scope-narrowing.
- All work fits within the smoke-test scope agreed at the outset; no deadline risk introduced.

## 7. Next Steps
1. **Sidecar rebuild** — required before any GUI-level testing of today's ingestion changes; not yet performed, per Section 5.
2. **Verify `FileUploader.tsx`'s file dialog filters** allow `.tif`/`.tiff` selection before attempting a GUI smoke test — outstanding question, source not yet reviewed this session.
3. **Proceed to Day 54** (README) as originally planned, folding this report's findings into the handover documentation: GeoTIFF/HDF are ingestion-only (Tier 1), not full-pipeline-supported, and this should be stated plainly rather than implied as complete.
4. **Day 56 exit-criteria check** should explicitly list HDF4 corner+resolution grids and GeoTIFF Tier 2 (query/stats/raster) as known, documented limitations — consistent with how Sea Ice Concentration and TSM/SSC were already handled.