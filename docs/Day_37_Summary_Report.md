# Day 37 Summary Report — OC-ECV Local Engine

**Date:** August 26, 2026 (Phase 4, Day 37)
**Phase:** 4 — Export Engines & Advanced Utilities
**Status:** Complete — raw data matrix export (.bin, CSV) implemented for both flat-grid and swath file structures; two TypeScript compile-time issues found and fixed before runtime; all 7 planned tests passed

## 1. Objective
Implement raw data matrix export (.bin, CSV tables), per the milestone's Phase 4 Day 37 item — the first Phase 4 export path operating on actual physical-unit pixel data rather than rendered visual output (Day 36's PNG/JPEG).

## 2. Design Decisions

- **Reused, not duplicated, Day 23's subsetting pipeline.** New `backend/processing/raw_export.py` calls `statistics.py`'s `_get_subsetted_data()` directly — the same structure-detection, spatial subsetting, temporal filtering, and quality-flag masking used by `/stats`, `/raster`, `/histogram`, and `/scatter` — rather than reimplementing any of it.
- **Long-format CSV for both structures.** A grid-matrix CSV (rows=lat, cols=lon) only makes sense for flat-grid files; swath's non-rectilinear per-pixel lat/lon has no natural row/column mapping. Long format (`lat,lon,value` per row) generalizes to both structures at the cost of repeating lat/lon per row — an acceptable tradeoff since CSV export isn't a bandwidth-sensitive path the way `/raster`'s binary payload is. NaN/masked pixels excluded entirely, consistent with Day 23's swath point-encoding convention.
- **New `.bin` layout, distinct from Day 23's.** Day 23's `encode_points_binary()` sends *normalized* 0-1 values for colormap rendering — wrong for analysis/GIS use, which needs physical units. New layout: flat-grid gets `[uint32 n_rows][uint32 n_cols][float64 lat_min/max][float64 lon_min/max][float32 values...]`, row-major, NaN *preserved* (grid position matters here, unlike swath); swath gets the same lon/lat/value contiguous-block triplet as Day 23's points binary, but unnormalized and without the `MAX_POINTS` stride-subsampling Day 23 applies for render payloads — this is a completeness-first analysis export, not a render payload.
- **New `/export-raw` endpoint, `/raster` untouched.** Zero regression risk to the working Day 23 visualization path — same discipline as Day 18's separate cached wrapper around `compute_regional_stats()`.
- **Frontend reused Day 36's save pattern, didn't fork it.** New `dataExport.ts` fetches from `/export-raw` and hands the result to Day 36's `saveFile.ts` unchanged. New `RawExportButton.tsx` kept as a separate component from Day 36's `ExportButton` (different format enum, `"csv"|"bin"` vs `"png"|"jpeg"`) rather than genericizing a component that already works, mirroring the same "add alongside, don't modify" approach used for the backend endpoint.
- **New `lastQuery` state in `App.tsx`.** Raw export reuses the exact query object last submitted via "Run Query," not the form's current (possibly edited-but-not-run) field values — ensures exported data always matches what's actually on the map/in `statsResult`.

## 3. Work Completed

**Backend (`backend/processing/raw_export.py`, new module)**
- `encode_csv_long()` — long-format CSV, branches on `structure_type` to `np.meshgrid()` flat-grid's 1D axis coordinates vs. using swath's already-2D per-pixel coordinates directly. Uses `np.savetxt` over a `StringIO`, not a row-by-row Python loop, given Day 16's stress-test grids ran into the millions of pixels.
- `encode_bin_flat_grid()` — raw float32 grid, NaN preserved, north-up row ordering (row 0 = max lat) matching `raster.py`'s `encode_bitmap_png()` orientation convention exactly.
- `encode_bin_swath()` — raw float32 point triplets, same contiguous-block layout as Day 23, unnormalized, uncapped.
- `compute_raw_export()` — validates `format` (`csv`/`bin`) upfront before any subsetting work runs; dispatches to the correct encoder based on `structure_type`.

**Backend (`server.py`)**
- New `/export-raw` endpoint — same query parameters as `/stats`/`/raster` plus `format`; catches `RawExportError` alongside the existing `StatisticsError`/`QualityMaskError`/`IngestionError` set, returning 400 (not 500) on failure.

**Frontend**
- `services/backendApi.ts`: new `fetchRawExport()` — same `StatsQuery` shape as `computeStats()`/`fetchRaster()`, returns a `Blob` (not JSON) since the response body is raw text/binary.
- `utils/dataExport.ts` (new): `exportRawData()` — fetches, converts to `Uint8Array`, hands off to `saveFile.ts`.
- `components/RawExportButton/RawExportButton.tsx` (new): mirrors `ExportButton.tsx`'s structure with a `"csv"|"bin"` format selector.
- `App.tsx`: new `lastQuery` state, captured at query-submit time and reset on file change/re-ingest; `RawExportButton` rendered in the existing Query-tab `map-controls` block, gated on `lastQuery` being non-null.

## 4. Issues Found and Fixed

| # | Issue | Root Cause | Resolution |
|---|---|---|---|
| 1 | `npx tsc --noEmit` produced 24 cascading parser errors, all inside the new `RawExportButton` file, starting at the first JSX tag | File was created as `RawExportButton.ts`, not `.tsx` — a plain `.ts` extension can't parse JSX syntax, so every `<div>`, `<select>`, `<option>` etc. was misread as a comparison operator or the start of a regex literal, cascading into 24 distinct-looking but single-root-cause errors | Renamed file to `RawExportButton.tsx`; no code or import changes needed |
| 2 | `npx tsc --noEmit` error: `Type 'Promise<string \| null>' is not assignable to type 'Promise<void>'` at the `RawExportButton` usage in `App.tsx` | `exportRawData()` returns `Promise<string \| null>` (the saved file path, or `null` on dialog cancellation) — passed directly as `onExport`, whose prop type expects `Promise<void>`. Day 36's `MapView.tsx` `handleExportMap` avoided this same mismatch by not returning `saveBinaryFile`'s result at all | Wrapped the call in `App.tsx` as `async (format) => { await exportRawData(lastQuery, format); }`, discarding the return value explicitly — same shape as `handleExportMap` |

**Underlying lesson:** unlike Day 36, both issues here were caught entirely at the TypeScript compile-time gate (`npx tsc --noEmit`), before any runtime testing — consistent with the project's stated convention of running that check after any TS change, before `npm run tauri dev`. Neither required DOM/render-state inspection; both were straightforward type/tooling errors, not logic bugs.

## 5. Testing Summary — All 7 Planned Tests

**Backend curl verification (run before any frontend work, per convention):**

| # | Test | Result |
|---|---|---|
| 1 | CSV export — flat-grid file (`sample_oceancolor.nc`, bbox `[33,36,-124,-120]`, `chlor_a`) | ✅ Correct `lat,lon,value` header; 1026 valid data rows out of 1200 grid cells (30×40) — 174 NaN pixels correctly dropped |
| 2 | `.bin` export — same flat-grid file | ✅ Header decoded to `n_rows=30`, `n_cols=40`; file size (4840 bytes) matched the formula `8 + 32 + 30×40×4` exactly |
| 3 | CSV export — swath file (real `AQUA_MODIS...L2.OC.nc`, bbox `[8,16,82,90]`) | ✅ 69953 valid data rows; lat/lon values non-monotonic/non-repeating per row, confirming the swath (2D per-pixel) code path, not an accidental flat-grid meshgrid broadcast |
| 4 | `.bin` export — same swath file | ✅ Header decoded to `point_count=69953`, matching CSV's row count from an independent code path; file size (839440 bytes) matched `4 + 69953×4×3` exactly |
| 5 | Invalid `format` query parameter | ✅ HTTP 400 with a clear error message, not a 500 |
| 6 | Non-overlapping bounding box | ✅ HTTP 400 — caught earlier than expected, by `_get_subsetted_data()`'s own bbox-overlap guard rather than `RawExportError`'s "no valid pixels" path; both are valid 400 cases, noted as a design observation rather than a discrepancy |

**Frontend/app-level testing:**

| # | Test | Result |
|---|---|---|
| 1 | Run Query-tab query on flat-grid file → `RawExportButton` appears only after query runs | ✅ |
| 2 | Export CSV → inspect contents | ✅ |
| 3 | Export `.bin` → confirm size math from actual app-triggered request | ✅ |
| 4 | Switch to swath file → repeat both formats | ✅ |
| 5 | Switch tabs away/back → `lastQuery` and button state persist (Option A's always-mounted panel convention) | ✅ |
| 6 | Edit a bbox field post-query without re-running → export reflects the *last-run* query, not the unsaved edit | ✅ |
| 7 | "Change file" → button disappears until a new query runs on the new file | ✅ |

## 6. Outcome
- Raw data matrix export (.bin, CSV) is fully implemented and verified for both flat-grid and swath file structures, at full physical-unit precision, distinct from Day 23's rendering-oriented normalized encodings.
- Cross-format consistency (identical valid-pixel counts independently derived from CSV row counts and `.bin` header point counts) and exact byte-count math on both `.bin` outputs provided strong correctness signals beyond visual inspection alone.
- Both issues found this session were caught at the TypeScript compile-time gate, before touching the running app — a faster and cheaper class of bug than Day 36's DOM-level issues, attributable to following the project's established `tsc --noEmit`-before-`tauri dev` convention.
- `/raster` and all other existing endpoints remain untouched — zero regression risk introduced to working Day 23/25-28 paths.
- All Phase 4, Day 37 exit-criteria items met: users can export raw numeric pixel data as CSV or binary, verified against real flat-grid and swath sample data, including the bbox-edit-without-resubmit edge case specific to the new `lastQuery` state.
- No known issues carried forward from this feature.

## 7. Next Steps (Day 38)
Implement georeferenced raster export (.tif / GeoTIFF or NetCDF subset export) — the next Phase 4 milestone item, extending raw numeric export into a GIS-interoperable spatial format, to be validated against external GIS software (QGIS) during the Day 40-42 buffer/review window.