# Day 31-35 Summary Report — OC-ECV Local Engine

**Date:** August 20-24, 2026 (Phase 3, Days 31-35 — Integration & Stress Testing)
**Phase:** 3 — Visualization & Interactive UI Dashboards
**Status:** Complete — Phase 3 exit criteria met; one item (sidecar-death crash) carried forward as monitored, not resolved

## 1. Objective
Per the milestone doc's Phase 3 closing scope: "Connect visualization layers with backend processing outputs; optimize render speeds for large grids." Final block before the Week 5 / Phase 3 exit-criteria checkpoint (August 24). Scope for this block, decided at session start: end-to-end regression, sidecar-crash stress testing, large-grid render performance, and wiring Phase D's previously-built-but-unused directory date-coverage scan into the UI.

## 2. Day 31 — End-to-End Regression
**Objective:** Regression-test all four modes (Query/Time Series/Histogram/Scatter) against both file structures (flat-grid, swath), with specific attention to the highest-risk recent changes: Day 30's `pickable:true`/tooltip work and the two `BboxDrawTool.ts` fixes.

**Testing performed (manual, live desktop app):**
- All 4 modes × both `sample_oceancolor.nc` (flat-grid) and `real_sample_data/AQUA_MODIS.20260101T092501.L2.OC.nc` (swath) — stats/raster/legend/opacity/colormap/tooltip, time-series (within-file + correctly-disabled-for-swath), histogram, scatter.
- Cross-tab Option A bbox independence (no bleed between tabs).
- File-switch remount behavior (Day 25's fix).
- Targeted retest of the exact terra-draw crash sequence from Day 30 (select a drawn rectangle, then edit a bbox field while it remains selected).

**Result:** Zero failures across the full matrix, including both targeted regression-risk spots. No code changes required.

## 3. Day 32 — Sidecar-Death Stress Test
**Objective:** Reproduce and root-cause the previously flagged crash (`Connection terminated unexpectedly` on `/stats`/`/raster` after rapid successive queries), specifically through Tauri's own spawn context — the earlier inconclusive test had only verified the standalone compiled binary, not the actual production spawn path.

**Testing performed:**
- Rapid-fire (~15-20+ back-to-back, no wait between requests), through `npm run tauri dev`, against `AQUA_MODIS.20260101T092501.L2.OC.nc` — the exact file that triggered the original crash.
- Same rapid-fire pattern repeated against `AQUA_MODIS.20260101T092501.L2.SST.nc` for broader coverage.
- An earlier round of interactive (non-rapid) testing against the SST file via the bbox draw tool also completed cleanly, and separately suggested the previously-deferred bbox preview stuttering issue (Phase C) may no longer be occurring.

**Result:** Zero errors, zero sidecar death, clean terminal output on both files under genuine stress conditions this time. **Not marked resolved** — no code change targeted this issue, and per this project's established concurrency-bug standard (Day 16), a clean stress pass is meaningful evidence but not proof of absence for an intermittent, previously-observed failure. Status: **monitored, not reproduced under dedicated stress testing on Aug 21, 2026.** If it recurs, capture Tauri's own piped stdout/stderr at the moment of failure (not a standalone-binary test).

Similarly, the bbox preview stuttering (deferred since Phase C) is logged as **observed improved, root cause unconfirmed** — no fix was applied, so this is not closed out as resolved.

## 4. Day 33 — Large-Grid Render Performance
**Objective:** Confirm raster rendering and Day 30's tooltip lookup (`decodeRawBitmapValues`) stay responsive at scale, using the existing 1.9GB synthetic fixture (`large_sample_oceancolor.nc`, regenerated as needed since Day 16 — confirmed already present on disk this session) and Day 23's 1024px downsampling cap.

**Testing performed:**
- Full query (Run Query) against the 1.9GB file through the live UI.
- Tooltip hover on the resulting large-grid raster.
- Repeat identical query to confirm cache-hit behavior (Day 18) holds at this scale.
- Browser DevTools inspection confirming the rendered raster's actual pixel dimensions respect the 1024px downsampling cap.
- Colormap/opacity switch responsiveness on the large raster.

**Result:**
- Cold query: raster rendered in ~6-7 seconds, no UI stutter or freeze.
- Tooltip hover: responsive, no lag, at full scale.
- Cached repeat query: confirmed hitting the SQLite cache with the expected large speedup, consistent with Day 18's original ~55x benchmark holding at scale, not just on small files.
- Downsampling cap: confirmed actually engaging (rendered dimensions capped, not a raw 4000×5000 paint).
- Colormap/opacity: instant, client-side, zero refetch, unchanged from Day 23/24 behavior.

No bugs found; no code changes required.

## 5. Day 34 — Wire "Use Full Directory Coverage" Toggle
**Objective:** Phase D (built during the Day 22-30 block) delivered `scan_directory_date_coverage()`, the `/batch-date-coverage` endpoint, and a tested `scanDateCoverage()` frontend client wrapper — but no UI component consumed it. This day closed that gap.

**Work completed (`frontend/src/components/TimeSeriesPanel/TimeSeriesPanel.tsx`, `.css`):**
- Added `useFullCoverage`/`coverageInfo`/`coverageLoading`/`coverageError` state.
- `runCoverageScan()` calls `scanDateCoverage()` on toggle-on or on directory selection (whichever happens second), auto-filling `startDate`/`endDate` from the scan's `overall_start`/`overall_end` on success.
- Graceful fallback: on scan failure or a directory with no usable time info, the toggle automatically unchecks itself and reverts to manual date entry, with an inline error shown.
- When enabled, the manual `DatePickerField` pair is replaced with a coverage summary line (start/end range, file count with usable time info) and an explanatory note.
- No backend changes required — `server.py`'s `/batch-date-coverage` and `backendApi.ts`'s `scanDateCoverage()` (from Phase D) matched the needed shape exactly.

**Testing performed (manual, against `backend/real_batch_data/`, the 25-file real MODIS batch fixture):**
| Test | Result |
|---|---|
| Toggle ON before picking a directory | ✅ Scan fires on directory selection, coverage summary displays correctly (`2026-01-01T09:25:01.469000` to `2026-01-10T10:19:59.528000`, 25/25 files) |
| Toggle ON after a directory is already picked | ✅ Scan fires immediately on check |
| Toggle OFF reverts to manual entry | ✅ Manual date fields reappear correctly |
| Real batch query using auto-filled coverage dates | ✅ Correct batch chart rendered (bbox lat 8-15/lon 82-90, `chlor_a`) |
| Graceful fallback on a directory with no usable time info | ✅ Correct error shown (`⚠ No files with usable time information found in this directory.`), toggle auto-unchecked |

`npx tsc --noEmit` clean throughout; no sidecar rebuild needed (frontend-only change).

## 6. Day 35 — Buffer & Review: Phase 3 Exit-Criteria Sign-Off

| Exit criterion (per milestone doc) | Status | Evidence |
|---|---|---|
| Interactive map displays geospatial raster layers with custom color maps | ✅ Met | Days 22-24 (build), Day 31 (regression) |
| Time-series trendlines and histograms update dynamically upon running a query | ✅ Met | Day 25 (time-series build), Days 26-28 (histogram/scatter build — see separately filed `docs/Day_26-28_Summary_Report` / `docs/Day_29_Summary_Report`), Day 31 (regression) |
| UI handles memory efficiently without browser/desktop crashes | ⚠️ Conditionally met | Day 33 (1.9GB fixture, clean, no freeze). Day 32's dedicated stress test found no reproduction under genuine rapid-fire load through Tauri's actual spawn context — but the one prior sidecar-death occurrence remains unresolved at the root-cause level and is carried forward as monitored, not closed |

**Phase 3 is functionally complete against all three exit criteria**, with one item explicitly flagged rather than silently closed: the sidecar-death crash has not recurred under two rounds of dedicated stress testing (Day 32, plus the original 11-trial standalone-binary test from the prior session) but was also never root-caused, so it is not being marked resolved.

## 7. Bugs Found and Fixed This Block
None. Days 31-35 surfaced zero new defects — every test across regression, stress, and large-grid performance passed cleanly, and the one new feature (Day 34's coverage toggle) was implemented and verified without requiring a fix-iteration cycle.

## 8. Carried-Forward Items (unchanged status, explicitly not closed)
1. **Sidecar-death crash (§9, originally flagged during Day 30):** monitored, not reproduced under dedicated stress testing (Day 32). If it recurs, capture Tauri's own piped stdout/stderr at the moment of failure.
2. **Bbox preview stuttering (deferred since Phase C):** observed improved during Days 31-32 testing; no root-caused fix applied, cause unconfirmed. Worth checking for any WSLg/system-level changes (Windows/WSL updates, GPU driver) that may correlate, without assuming causation.
3. **Query cache code-version awareness (documented since Day 19-21):** still not fixed — cache keys do not account for backend logic changes, meaning a stale cached result could theoretically be served after a code change without a corresponding cache-clear. Not touched this block; still a real, documented gap.
4. **Sea Ice Concentration / TSM/SSC ECV coverage:** still deferred (access/availability issues, documented since Day 19-21). Out of scope for Phase 3; remains a Phase 4/5 consideration if time allows before the Sept 15 deadline.

## 9. Outcome
- Days 31-35 executed sequentially and individually, per the project's established one-day-one-objective discipline, despite the calendar compression of running this block within a single working session on August 23-24, 2026.
- Full regression, dedicated concurrency/crash stress testing, and large-file render performance all verified clean against real and synthetic data.
- Phase D's previously-orphaned coverage-scan feature is now fully wired into the UI, closing out the last "built but unused" item carried from the Day 22-30 block.
- Phase 3 (Visualization & Interactive UI Dashboards) is complete against its three formal exit criteria, with one known, non-blocking item explicitly carried forward rather than silently dropped — consistent with this project's standing practice of honest deferral over false closure.
- Zero schedule slippage relative to the September 15, 2026 MVP deadline.

## 10. Next Steps (Phase 4, Week 6 — Day 36 onward)
Begin Phase 4: Export Engines & Advanced Utilities — high-resolution PNG/JPEG export, raw data matrix export (.bin, CSV), georeferenced raster export (.tif/NetCDF), and the processing-history panel (which can reuse Day 18's `query_cache` SQLite table structure directly, per that day's original design intent). Worth scheduling the cache-key-versioning fix (§8 item 3) early in this phase, before more caching-dependent features are added on top of it.