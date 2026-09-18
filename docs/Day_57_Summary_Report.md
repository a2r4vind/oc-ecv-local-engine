# Day 57 Summary Report — OC-ECV Local Engine

Date: September 17, 2026 (Post-MVP — Mentor-Requested Priority Item)
Phase: Post-MVP — Mentor-Requested Additions
Status: ✅ Complete — both Oceansat-3 OCM-3 chlorophyll products verified end-to-end

## 1. Objective
Per the mentor's 16 September directive — sent in response to the six post-MVP items originally proposed, and superseding their priority order — integrate real ISRO EOS-06/Oceansat-3 OCM-3 chlorophyll data into the existing ingestion/query/visualization pipeline ahead of every other pending item: *"download few Oceansat-3 OCM chlorophyll data and implement in your GUI. This is required on priority!"*

## 2. Data Acquired

- **`EOS-06_OCM(GAC)_L2C-Chlorophyll`** — single-pass granule, Bhoonidhi portal, filters TL(25,58)/BR(4,80), 1–31 Aug 2026. File: `E06_OCM_GAC_01AUG2026_213082406011_19438_STGOCLHND_46_15_F/BAND.nc`
- **`EOS-06_OCM(GAC)_Chlorophyll_8day_4km`** — global 8-day composite, 1–8 Aug 2026. File: `E06_OCM_GAC_01AUG2026_08AUG2026_8_T000000_MGG0CLHND_4km/BAND.nc`

Both selected over their LAC/L2C-only counterparts specifically for higher odds of a working, demo-able result within the available runway (8-day compositing fills single-pass cloud gaps; GAC's smaller file size favors faster iteration than LAC).

## 3. Structural Findings (inspected before any code change, per project's "never patch blind" discipline)

**L2C product:**
- Flat-grid, no groups, 1D lowercase `latitude`/`longitude` coordinates (1587×1667)
- Variable name `CL-a` (hyphenated) — not matched by any existing `KNOWN_ECV_PREFIXES` entry
- `_FillValue=-999.0`, no `valid_min`/`valid_max` — clean CF decode via xarray's default `decode_cf`; not a repeat of Day 20's SST valid-range bug, since no such attributes exist on this file to be silently ignored
- Descending latitude, standard -180/180 longitude — both already handled correctly by existing order-agnostic subsetting code

**8-day composite:**
- Flat-grid, no groups, but **capitalized** `Latitude`/`Longitude` coordinate names (4321×8641, global coverage)
- Variable name `chl` — too short to match any existing prefix via `startswith` (shorter than every listed prefix)
- int16 storage with `scale_factor`/`add_offset` (0.001, 0.0) + `_FillValue=-32768` — correctly auto-decoded by both `netCDF4` and xarray's default CF handling; decoded values (0.001–10.0 mg/m³) physically sane against the product's own browse-image legend
- **4D array shape** `(Time=1, Depth=1, Latitude, Longitude)` — singleton non-spatial leading dimensions, unlike every prior real product tested in this project (all previously 2D or 3D-with-genuine-timesteps)
- Near-empty global attributes (no `geospatial_lat/lon_min/max` fallback available if coordinate-based extraction failed)
- Coordinate arrays overshoot physical bounds by float32 grid-step rounding (`90.00015`/`180.00030` instead of exact `90`/`180`) — grid-construction noise, not real data past the pole/antimeridian

## 4. Code Changes

**`backend/ingestion/netcdf_reader.py`**
- `KNOWN_ECV_PREFIXES["chlorophyll"]`: added `"cl-a"`, `"chl"`
- `extract_metadata()`: lat/lon coordinate-name lookup made case-insensitive (previously exact-match `"lat"`/`"latitude"` only); reported lat/lon range now clipped to physical `[-90,90]`/`[-180,180]` bounds to absorb float32 grid-construction overshoot without masking a genuine out-of-range condition elsewhere

**`backend/processing/statistics.py`**
- `_get_lat_lon_names()`: same case-insensitive fix, returning the file's actual variable casing (e.g. `"Latitude"`) so downstream bracket access (`ds[lat_name]`) still resolves correctly

**`backend/processing/raster.py`**
- `encode_bitmap_png()`: squeeze logic generalized from a hardcoded `ndim==3` check to any array carrying singleton leading dimensions beyond the trailing `(lat, lon)` axes — fixes a crash (`ValueError: too many values to unpack`, inside `_downsample_2d()`) on the 8-day composite's 4D array. Original real-timestep behavior (`ndim==3`, take index 0) preserved unchanged; any other unexpected shape now raises a clear `RasterError` instead of an unhandled exception.

## 5. Verification (source → compiled sidecar → live UI, per project standard)

**L2C file:**
- Source-level ingest: `ecv_variables.chlorophyll: ["CL-a"]`, `validation.valid: true`
- `/stats` via sidecar (bbox lat `[-5,-1]` lon `[48,53]`, pre-computed as a known-good high-validity region): `valid_fraction: 0.8701`, `mean: 0.4476` — confirmed identical across two calls (`_cache_hit: false` then `true`)
- UI: map render, colormap/opacity/legend, stats panel all confirmed via live screenshot

**8-day composite file:**
- Source-level ingest (pre-fix): `LAT_OUT_OF_RANGE`/`LON_OUT_OF_RANGE` validation errors (float32 overshoot) — investigated and root-caused before assuming a validator bug
- Source-level ingest (post-fix): `validation.valid: true`, `lat_range: [-90.0, 90.0]`, `lon_range: [-180.0, 180.0]`
- `/stats` via sidecar (bbox lat `[-5,-1]` lon `[48,53]`): `valid_fraction: 1.0`, `mean: 0.4071` — confirmed identical across two calls
- `/raster`: crashed pre-fix (500, `ValueError` in `_downsample_2d`); confirmed rendering correctly in the live UI post-fix
- Histogram tab: confirmed working, **no code change required** — traced by hand: boolean-mask indexing (`values[~np.isnan(values)]`) flattens regardless of array `ndim`, so the existing `ndim==3` time-squeeze in `compute_histogram()`/`compute_scatter_correlation()` being skipped for this 4D file has no numeric effect on the result
- Scatter tab: correctly refused with *"Select two different variables to correlate"* — both files carry exactly one classified variable, so this is expected, correct behavior, not a defect

## 6. Outcome
- Mentor's priority item — real Oceansat-3 OCM-3 chlorophyll data, multiple files, working in the GUI — is complete: two structurally distinct real products (single-pass L2C, global 8-day composite) verified end-to-end across ingest, validation, stats, raster map rendering, histogram, and scatter's correct-refusal path.
- Three real structural surprises were found and fixed in this integration (hyphenated/short variable names, capitalized coordinate names + float32 grid-overshoot, singleton-leading-dim array shape) — on the higher end of, but consistent with, this project's established pattern that every new real-satellite-product integration surfaces at least one genuine surprise.
- All changes are minimal, targeted, and verified via source → compiled sidecar → live UI at each step.
- Demo clip prepared for mentor review; awaiting his response before resuming remaining post-MVP items.

## 7. Not Done / Flagged, Not Fixed
- **No full-stack regression re-run** (Day 43-style sweep) against the 11 previously-verified real ECV products, to independently confirm the case-insensitive lat/lon lookup and new prefix entries introduce zero regressions elsewhere. Risk assessed as low — both changes are additive (new prefix entries, broadened rather than replaced matching logic) — but not independently verified this session. Recommended as a quick spot-check before final handover of this change set.
- AppImage not rebuilt with today's changes — verification was performed entirely in dev mode (`npm run tauri dev`) through the compiled sidecar, consistent with the project's verification standard; packaging deliberately deferred until the mentor's response determines whether further changes are imminent.

## 8. Next Steps
Await mentor response to the Oceansat-3 demo clip. Resume remaining post-MVP items in order: #1 (adjustable color-scale increments), #2 (manual graticule lat/lon range), #4 (send a follow-up clip demonstrating already-implemented batch mode), #3 (pending mentor clarification on "statistics options"), #6 (research paper — pending mentor's license decision), then final internship report and LOR draft, ahead of the September 21, 2026 internship-end date.

---

## Addendum (September 18, 2026): Mentor Item #3 — Additional Statistics

### 1. Objective
Implement mentor item #3 ("statistics options"), clarified in prior discussion as additive-only: extend the existing statistics set (mean, min, max, std, valid_fraction, valid_pixel_count — all left completely unchanged) with median, geometric mean, P25/P75, IQR, skewness, and coefficient of variation (CV).

### 2. Design Decisions Made Before Implementation
- **Plain NumPy over scipy.** Skewness (Fisher-Pearson third standardized moment, population convention, `ddof=0` to stay consistent with the existing `std`) was implemented as a manual moment calculation rather than pulling in `scipy.stats.skew` — confirmed first that `statistics.py` had no existing scipy dependency, and adding one this close to handover for a single statistic wasn't justified.
- **Geometric mean guarded, not assumed safe.** Chlorophyll-a and other ECV concentrations are physically positive, but `compute_statistics()` doesn't assume this — geometric mean is only computed when every valid pixel in the region is strictly positive; otherwise returns `None` rather than raising or producing `nan`/`inf` silently. Motivated directly by the domain literature: chl-a is classically log-normal in ocean color science, which matches the heavy right-skew already observed empirically in real Oceansat-3 data (mean ~0.4-0.6 mg/m³ against maxima in the 90s mg/m³) — geometric mean is the domain-standard central-tendency measure for this distribution shape, not an arbitrary addition.
- **Degenerate-case handling for skewness/CV.** Skewness returns `None` when `std == 0` (a constant-valued region has no skew, and dividing by zero std would otherwise produce `nan`). CV (`std/mean`) returns `None` when `mean == 0`, for the same reason.
- **Zero backend structural changes beyond the one function.** All additive fields are computed inside `compute_statistics()`, the single shared numeric core every stats-producing endpoint (`/stats` and its cached wrapper) already funnels through — no endpoint, cache-key, or dispatch logic required any changes.

### 3. Work Completed

**Backend (`backend/processing/statistics.py`)**
- `compute_statistics()` extended: added `median`, `geometric_mean`, `p25`, `p75`, `iqr`, `skewness`, `cv` to both the zero-valid-pixel branch (all `None`) and the normal branch, alongside the original six untouched fields.

**Frontend (`frontend/src/App.tsx`)**
- Stats panel JSX extended with six new rendered rows (Median, Geometric Mean, P25/P75, IQR, Skewness, CV), with explicit fallback text for the two nullable-by-design fields (`"n/a (non-positive values present)"` for geometric mean, `"n/a (constant region)"` for skewness, `"n/a (mean = 0)"` for CV) rather than rendering blank or `NaN`.

**Frontend (`frontend/src/services/backendApi.ts`)**
- `StatsResult` interface extended with the same seven fields (all optional, nullable), matching the backend's response shape exactly.

### 4. Verification
Verified end-to-end per this project's established standard — source → compiled sidecar → live UI:
- Sidecar rebuilt via the standard routine (backend file changed).
- `npx tsc --noEmit` clean before `npm run tauri dev`.
- Live UI: ran real queries against Oceansat-3 chlorophyll data; confirmed all thirteen statistics fields (six original + seven new) render correctly, geometric mean sits below the arithmetic mean as expected for a right-skewed distribution, and the existing six original fields are byte-for-byte unchanged from pre-addendum behavior.
- AKV confirmed end-to-end pass.

### 5. Outcome
- Mentor item #3 complete: six new statistics (median, geometric mean, P25/P75, IQR, skewness, CV) added alongside the existing six, verified against real Oceansat-3 data, with domain-appropriate handling for chlorophyll's log-normal distribution shape and defensive guards against non-positive values, zero-std, and zero-mean edge cases.
- No regressions to any existing statistics field or any other endpoint — change was fully additive and isolated to one shared function plus its two direct consumers (stats panel rendering, `StatsResult` typing).
- Items #1, #2, #4, and #5 (Oceansat-3) are all complete; item #3 now joins them. Remaining: item #6 (research paper — license decision still pending mentor), final internship report, LOR draft/request.

### 6. Next Steps
Send mentor a status update confirming items #1-#5 are all complete and verified (with item #3 folded into this same demo/summary rather than a separate email, consistent with how #1/#2 were bundled). Await mentor's license decision (MIT/Apache/GPL) to unblock item #6. Begin drafting the final internship report, reusing the Day 56 report and milestone doc as the base per the existing plan.