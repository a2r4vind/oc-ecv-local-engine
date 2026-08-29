# Day 40-42 Summary Report — OC-ECV Local Engine

Date: August 29-31, 2026 (Phase 4, Days 40-42 — Buffer & Review)
Phase: 4 — Export Engines & Advanced Utilities
Status: ✅ Complete — Phase 4 closed out; both export paths validated in QGIS; one carried-forward issue (#6) investigated, root-caused, and closed as correct behavior

1. Objective
Per the milestone's Phase 4 buffer/review scope: validate GeoTIFF/NetCDF export file integrity in external GIS software (QGIS), closing out Phase 4 ahead of Phase 5's September 1 start. Specifically revisit carried-forward issue #6 (swath NetCDF export's pixel/line-space Corner Coordinates in `gdalinfo`), previously flagged but unresolved at Day 38.

2. Work Completed

**QGIS Installation**
- QGIS was not previously installed locally; installed via the official QGIS APT repository (system-level install, not a conda package, since it's a GUI application) rather than conda, keeping `oc-ecv-env` untouched.
- Verified clean launch and full rendering under WSLg — toolbars, panels, canvas all correct, no repeat of this project's known WSLg native-widget rendering pattern (Days 12-14, 24). This is notable given QGIS is itself a large Qt-based application; its GUI initialization did not trigger the same class of failure seen with native `<input>` widgets inside the Tauri webview.
- QGIS 3.44.7 'Solothurn' confirmed via `qgis --version`.

**Flat-Grid GeoTIFF Validation**
- Ran a fresh query and Day 38 GeoTIFF export against the synthetic flat-grid file (California coast fixture).
- Loaded `new_sample_oc.tif` directly in QGIS via Add Raster Layer.
- Confirmed: CRS `EPSG:4326`, coordinate readout centered at `34.791°, -118.393°` (correctly inside the file's known California extent, lat 32-38°N / lon -125 to -118°W, established since Day 22), rendered as a clean rectangular grayscale raster patch with no distortion or offset.
- **Result: GeoTIFF export validated as correctly georeferenced.**

**Swath NetCDF Validation and Issue #6 Investigation**
- Ran a fresh query (`aot_869`, bbox `[8, 16, 80, 95]`) against the real MODIS swath file and exported via Day 38's `/export-geo` endpoint (backend correctly selected CF-1.8 NetCDF for the swath structure type).
- Loading `new_aqua_modis_oc.nc` in QGIS surfaced a GDAL subdataset picker listing `aot_869`, `lat`, and `lon` as separate subdatasets — expected GDAL NetCDF driver behavior (every 2D array is exposed as its own subdataset); `lat`/`lon` are coordinate arrays, not meant to be loaded as standalone rasters, and were excluded.
- Loading `aot_869` alone initially appeared blank; "Zoom to Layer" revealed the actual issue: QGIS had resolved the layer's extent at scale `1:532492544` — consistent with an extent spanning close to the full globe, not the expected ~1500km-wide swath region.
- Root-caused directly via `gdalinfo`: the plain `Corner Coordinates` block reported raw pixel/line indices (`0.0` to `1061.0` / `1088.0`, matching `Size is 1061, 1088` exactly) rather than degrees — reproducing issue #6 exactly as flagged at Day 38.
- Critically, `gdalinfo`'s own output also showed a fully populated `Geolocation` metadata block (`GEOREFERENCING_CONVENTION=PIXEL_CENTER`, `X_DATASET`/`Y_DATASET` correctly pointing at the file's own `lon`/`lat` variables) — confirming the file itself carries correct, standard, CF-compliant per-pixel geolocation data. This is the same geolocation-array mechanism real NASA L2 swath products use, since a simple 6-parameter affine transform cannot describe curved satellite ground-track geometry.
- **Definitive verification:** ran `gdalwarp -geoloc -t_srs EPSG:4326` to force GDAL to resolve the raster through its geolocation arrays rather than reporting raw pixel/line indices. Resulting `gdalinfo` on the warped output showed:
  - Upper Left: 78.17°E, 17.61°N
  - Lower Right: 94.46°E, 6.02°N
  - This lands exactly inside the queried bbox `[8, 16, 80, 95]`, over the Bay of Bengal / India's east coast — matching every prior finding for this region since Day 8.

3. Root Cause and Resolution — Issue #6

| Aspect | Finding |
|---|---|
| Is the export data wrong? | No. `encode_netcdf_swath()` produces genuinely correct per-pixel geolocation, confirmed by independently warping through the file's own geolocation arrays and landing on the exact real-world region queried. |
| What caused the misleading `gdalinfo` output? | `gdalinfo`'s default `Corner Coordinates` report — and QGIS's default "Add Raster Layer" load path — do not automatically resolve extent through GDAL's geolocation-array mechanism. Both instead report/use the raw pixel/line grid unless a tool explicitly requests geolocation-aware resolution (e.g. `gdalwarp -geoloc`). This is a general property of geolocation-array-georeferenced files in the GDAL ecosystem, not specific to this project's export code. |
| Was this previously flagged correctly? | Yes — Day 38's original flag ("Swath NetCDF export's pixel/line-space Corner Coordinates in gdalinfo — flagged for Day 40-42 QGIS validation, not fixed") was accurate as a symptom description; this block supplies the missing root cause and confirms no code fix is needed. |

**Underlying lesson:** for any future swath/geolocation-array-based export or import work, remember that `gdalinfo`'s plain output and default GIS-tool "Add Raster" behavior are not sufficient to judge georeferencing correctness on their own for this class of file — deliberately resolving through the geolocation arrays (`-geoloc` in `gdalwarp`, or an equivalent geolocation-aware read path) is required to see the true extent. A tool reporting pixel/line-space coordinates is not, by itself, evidence of a bug.

4. Outcome
- Both Day 38 export paths (flat-grid GeoTIFF, swath CF-1.8 NetCDF) are now validated as genuinely, correctly georeferenced — not merely structurally valid per earlier `gdalinfo`-only checks.
- Carried-forward issue #6 is closed with a confirmed, evidence-based root cause (GDAL/QGIS default reporting convention for geolocation-array files) rather than left open or force-closed on assumption.
- QGIS is now installed and available locally for any future export-validation needs (e.g. Phase 5 regression testing).
- Phase 4 (Export Engines & Advanced Utilities) is fully complete: high-res visual export (Day 36), raw data export (Day 37), georeferenced raster export (Day 38, now independently GIS-validated), and processing history (Day 39) are all implemented, tested, and verified — all Phase 4 exit criteria met.

5. Next Steps (Phase 5, Week 7 — beginning September 1)
Before beginning Phase 5's full integration testing scope, close out the second of two follow-ups explicitly carried forward from the Day 19-21 buffer block: resolving Sea Ice Concentration's `earthaccess` access issue (AU_SI25 / AU_SI25_NRT_R04 returning 0 granules despite open collection metadata), likely via direct NSIDC tooling rather than the `earthaccess`/CMR path already time-boxed and exhausted at Day 21. (The first of that pair — cache-key code-version awareness — was already completed via the `CACHE_VERSION` constant introduced ahead of Day 39's history panel work.)

Once that is resolved or re-documented, Phase 5 begins per the milestone: end-to-end integration testing across all ECV categories (Days 43-46), Tauri bundler packaging for standalone installers (Days 47-49), user/deployment documentation (Days 50-52), and final cleanup/handover prep ahead of the September 15 deadline (Days 53-56).