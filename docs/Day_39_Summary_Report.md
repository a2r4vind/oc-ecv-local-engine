# Day 39 Summary Report — OC-ECV Local Engine

**Date:** August 28, 2026 (Phase 4, Day 39)
**Phase:** 4 — Export Engines & Advanced Utilities
**Status:** Complete — processing history panel implemented and verified at all three levels (source → compiled sidecar → live UI), zero bugs found, one pre-existing gap identified and formally deferred

## 1. Objective
Build a processing history panel tracking previous user queries and parameters, per the Phase 4 milestone item — giving users a way to browse and reload past queries rather than re-entering parameters from scratch.

## 2. Design Decision: Reuse Day 18's `query_cache` Table
No new storage layer was built. The Day 18 caching module's docstring explicitly anticipated this day ("Designed to double as the data source for Day 39's processing-history panel — same table, just needs a read/browse endpoint later"), and the schema already had everything needed: `created_at` (timestamp), `cache_version` (from the Day 39 prerequisite fix), and all query parameters (file path, variable, bbox, date range, quality flags) plus `hit_count`. No schema migration was required.

## 3. Work Completed

**Backend (`backend/caching/query_cache.py`)**
- `get_history(limit, offset)` — read-only browse function. Queries `query_cache` ordered by `created_at DESC`, returns query parameters and metadata (not `result_json` — reloading re-fires the actual endpoint, which hits cache and returns near-instantly per Day 18's ~55x measured speedup, rather than duplicating result payloads in the history response).

**New Endpoint (`backend/api/server.py`)**
- `GET /history` — accepts `limit`/`offset`, returns `{total, entries[]}`, sanitized via the standard `_sanitize()` NumPy-safety pattern used since Day 5.

**Frontend**
- `backendApi.ts`: `HistoryEntry`/`HistoryResult` types, `fetchHistory()`.
- New `components/HistoryPanel/HistoryPanel.tsx` + `.css` — styled to match `TimeSeriesPanel`'s established conventions (`--oc-*` design tokens, `.timeseries-note` reused for loading/empty states rather than duplicating a near-identical class).
- `App.tsx`: added `"history"` as a 5th sidebar tab following the existing permanently-mounted/`display:none` pattern; `bboxByMode.history` slot; `handleReloadHistoryEntry()`.

## 4. Design Decision: Cross-File Reload (Option B)
Two options were weighed before implementation: reload restricted to the currently-loaded file only (Option A) vs. full cross-file reload — re-ingesting a different file automatically if the selected history entry belongs to one (Option B). Option B was chosen as the better match for the Phase 4 exit-criteria language ("reloading past workflows instantly"), and was cheap to implement since `ingestFile()` was already exported and reusable from `backendApi.ts` outside `FileUploader` — no duplicate ingestion code path was introduced.

`handleReloadHistoryEntry()`:
1. If the entry's `file_path` differs from the currently loaded file, calls `ingestFile()` and routes through the existing `handleIngested()` state-reset path.
2. Sets `bboxByMode.stats` from the entry's bbox and switches `activeMode` to `"stats"`.
3. Calls `handleQuerySubmit()` directly with the historical parameters, bypassing `ParameterSelector`'s own form state entirely — same pattern as Day 37's `lastQuery` snapshot approach.

## 5. Bug Found and Fixed During Implementation
While wiring `bboxByMode`'s reset object literals for the new `"history"` mode, found that `handleIngested()` and `handleChangeFile()`'s existing reset objects were missing the new `history` key (a mechanical omission introduced by adding a 5th mode, not a functional regression) — same bug shape as prior stale-state issues (Day 24 opacity/pan reset, Day 25 sibling-key collision). Fixed by adding `history: null` to both reset literals before any UI testing began.

## 6. Verification

Consistent with the project's established standard: verify source → compiled sidecar → live UI, not source-only.

| Level | Test | Result |
|---|---|---|
| Source | `get_history()` against populated `query_cache.db` | ✅ Correct ordering, field shape |
| Compiled sidecar | `curl http://127.0.0.1:5321/history` (absolute paths) after rebuild | ✅ `total`/`entries` returned correctly; `created_at` descending confirmed by direct inspection, not assumed from the `ORDER BY` clause alone |
| Compiled sidecar | Repeated identical `/stats` query via curl, then `/history` | ✅ `hit_count` incremented correctly; `/history` itself does not inflate `hit_count` (read-only, confirmed) |
| Live UI | Run 2-3 varied queries across two different files | ✅ History tab lists all entries, correct order, correct file/variable/bbox/hit-count display |
| Live UI | Reload a same-file history entry | ✅ Map bbox rectangle, stats panel, and raster all update to match the historical query, not current form field state |
| Live UI | Reload a cross-file history entry | ✅ Correctly re-ingests the target file first (loaded-file bar updates), then runs the historical query |
| Live UI | Console check throughout | ✅ Clean — no errors, no React key warnings |

No bugs found during live UI testing — a clean first pass, consistent with the project's growing base of proven, reusable patterns (remount-on-file-change discipline from Day 25, `lastQuery`-style snapshotting from Day 37) being applied correctly from the start rather than rediscovered.

## 7. Gap Identified and Deferred: Quality Flags Not Forwarded

While reviewing `handleQuerySubmit`'s query construction for the reload path, confirmed that `qualityFlags` is not forwarded to `/stats` anywhere in the current frontend — not a Day 39 regression, but a **pre-existing gap dating to Day 15**, whose report explicitly noted quality flags were "not yet exposed in the UI, but the endpoint supports it for future use." No control in `ParameterSelector` has ever let a user select quality flags, so there has never been a value for `handleQuerySubmit` to forward. `HistoryPanel` correctly captures and displays `entry.quality_flags` (the caching layer has always stored it), but reloading cannot apply it, since the same limitation applies to every query path in the app, not just history-reloaded ones.

**Decision:** Log and defer to Phase 5 polish / buffer time, not fixed this block. Backend support (Day 10's flag definitions, Day 15's endpoint parameter, `StatsQuery.qualityFlags` typing) is already fully in place — the only missing piece is a flag-picker UI control in `ParameterSelector`, sourced from the file's own `l2_flags` definitions. Deferring avoids scope creep on a day that otherwise closed out cleanly, and keeps focus on the Day 40-42 buffer window's already-scoped QGIS validation work.

## 8. Outcome
- Processing history panel is implemented, verified at all three levels, and working correctly for both same-file and cross-file reload.
- Zero regressions in existing tabs (Query/TimeSeries/Histogram/Scatter) or the export flow.
- One mechanical bug (missing `history` key in two reset object literals) was caught and fixed before UI testing, not after.
- One real, pre-existing UI gap (quality-flag forwarding) was identified, root-caused to Day 15, and formally deferred with documented reasoning rather than silently left unaddressed or hastily patched under deadline pressure.
- All Phase 4, Day 39 exit-criteria items met: processing history panel built, allowing past workflows to be reloaded instantly via the existing SQLite cache's ~55x speedup on identical queries.

## 9. Next Steps (Days 40-42, Buffer & Review)
Phase 4's remaining buffer/review scope: validate GeoTIFF/NetCDF export file integrity in external GIS software (QGIS install still pending — verification so far limited to `gdalinfo`, confirmed available in `oc-ecv-env`). Also carries forward from Day 38: resolving the swath NetCDF export's pixel/line-space Corner Coordinates reporting in `gdalinfo` (expected for geolocation-array data, but worth confirming QGIS handles it correctly via `-geoloc` or manual subdataset layering). Quality-flag UI exposure remains logged as a Phase 5 polish candidate, not scheduled for the buffer window.