# Day 25 Summary Report — OC-ECV Local Engine

**Date:** August 14, 2026 (Phase 3, Day 25)
**Phase:** 3 — Visualization & Interactive UI Dashboards
**Status:** Complete — Tauri integration finished, four bugs found and fixed through live UI testing (two state-management, one React key-collision, one chart-layout), all verified via repeated manual test passes through the actual desktop app

## 1. Objective
Integrate a charting library (Plotly.js) for time-series anomaly trendlines, completing the Tauri wiring and UI integration that was in progress at the end of the prior session — the first place this project's flat-grid multi-time-step data is visualized across its full time dimension, and the first place multi-file batch aggregation (Day 17's `/batch-timeseries`) is rendered visually rather than as raw JSON.

## 2. Work Completed

**Backend (carried over from prior session, verified stable this session)**
- `compute_timeseries_within_file()` and `/timeseries-within-file` endpoint for flat-grid files with a time dimension.
- Reuses Day 17's `/batch-timeseries` endpoint for cross-file directory aggregation.

**`TimeSeriesPanel` Component (`frontend/src/components/TimeSeriesPanel/TimeSeriesPanel.tsx`)**
- Mode toggle between "Within this file" and "Batch across a directory," with "Within this file" correctly disabled (with an explanatory note) for swath files lacking a time dimension — consistent with the temporal-filtering rule established on Days 9 and 11.
- Directory picker (batch mode) reusing the `@tauri-apps/plugin-dialog` pattern from Day 5's file uploader.
- Custom date range fields reusing Day 12-14's `DatePickerField` component.

**`TimeSeriesChart` Component (`frontend/src/components/TimeSeriesChart/TimeSeriesChart.tsx`)**
- Plotly.js dual-axis chart: line+marker trace for the raw variable values, bar trace for anomaly (deviation from series mean) on a secondary y-axis.
- Shared by both within-file and batch modes via a `title` prop, avoiding two near-duplicate chart components.

**`App.tsx` Integration**
- `TimeSeriesPanel` wired in alongside the existing `MapView`/`ParameterSelector` flow, reading `availableVariables` and a `defaultBbox` derived from the current map bounding box.

## 3. Bugs Found and Fixed

Four bugs surfaced through live manual UI testing (loading real and synthetic files, switching between them, exercising both time-series modes) — none were caught by source-level testing alone, consistent with this project's established pattern that UI state bugs only reliably surface through the actual running app.

| # | Bug | Root Cause | Resolution |
|---|---|---|---|
| 1 | Switching to a newly loaded file left `TimeSeriesPanel`'s mode, directory, and error state from the *previous* file still showing (e.g. "Batch across a directory" pre-selected with the old directory path still filled in) | `TimeSeriesPanel` was added this session without the `key={ingestedFilePath}` remount pattern already established for `ParameterSelector` on Day 12-14 — React reused the same component instance across file switches instead of resetting its internal `useState` values | Added a `key` prop to `TimeSeriesPanel` so it fully remounts (fresh initial state) whenever the loaded file changes |
| 2 | Selecting a variable from the dropdown after a file switch silently submitted a *different*, stale variable value than what was visibly displayed (e.g. dropdown showed `chlor_a`, but the query sent `aot_869`) | Same root cause as #1 — the `variable` state's `useState(availableVariables[0] \|\| "")` initializer only runs once. On file switch without remounting, `variable` kept its old value (`aot_869`), which not being in the new file's option list, made the browser render the first available option (`chlor_a`) as a fallback display *without* updating the underlying React state — so the visible label and the actual state silently diverged | Resolved by the same remount fix as #1; a fresh mount re-runs the `useState` initializer against the new file's `availableVariables` |
| 3 | Fixing #1/#2 by adding `key={ingestedFilePath}` to both `TimeSeriesPanel` and `ParameterSelector` caused a *new* regression: each file load produced an additional stacked "Time Series" block instead of replacing the existing one, confirmed via a React console warning: `Encountered two children with the same key` | `TimeSeriesPanel` and `ParameterSelector` are sibling elements in the same JSX fragment; both were given the identical key expression `ingestedFilePath`. React requires keys to be unique *among sibling elements*, not merely unique per component type — an identical key on two different siblings breaks React's reconciliation and can duplicate or omit children, exactly as its own warning states | Prefixed each key uniquely per component (`` `timeseries-${ingestedFilePath}` `` and `` `params-${ingestedFilePath}` ``), preserving the remount-on-file-change behavior while eliminating the collision |
| 4 | X-axis time/filename labels overlapped and were partially clipped in both within-file and batch chart views, reported directly by AKV via screenshots across two separate test passes | Fixed plot `height`/`margin.b` were too small to accommodate rotated tick labels, and no `tickangle`/`automargin` was set — Plotly's default auto-rotation had no reserved space to render into | Increased chart `height` (360→480) and bottom `margin` (60→130), set explicit `xaxis.tickangle: -45` and `xaxis.automargin: true`, widened the container (640px→800px), and shifted the legend further down (`y: -0.25 → -0.35`) to clear the taller label area |

**Underlying lesson:** bug #3 is a new failure category for this project — the first bug traced to a React reconciliation/key mistake rather than the previously recurring classes (WSLg native-widget rendering, stale PyInstaller sidecar binaries, HDF5 concurrency). It surfaced only because the fix for bugs #1/#2 was applied to two sibling components using the same key expression without checking sibling-uniqueness — worth remembering that any future `key={ingestedFilePath}`-style remount fix must be namespaced per component when applied to siblings, not copy-pasted as-is.

## 4. Testing Summary

All testing was performed manually through the live desktop app (not source-only), per this project's established verification standard for UI-facing changes.

| Test | Result |
|---|---|
| Load real MODIS swath file (`AQUA_MODIS.20260101T092501.L2.OC.nc`) — mode toggle | ✅ "Within this file" correctly disabled with explanatory note; "Batch across a directory" selectable |
| Batch directory picker — select `real_batch_data/` folder | ✅ Full path correctly populated in Directory field |
| Load flat-grid synthetic file (`sample_oceancolor.nc`) after swath file, before fix | ❌ (bug #1/#2) Stale mode/directory/variable carried over from previous file |
| Same sequence, after remount fix | ✅ Mode resets to default, directory clears, variable list refreshes correctly |
| Repeated load of the same swath file 4× in one session, after remount fix (pre key-namespacing) | ❌ (bug #3) New "Time Series" block appended on each load; console confirmed key collision warning |
| Same test, after key-namespacing fix | ✅ Exactly one "Time Series" block, cleanly replaced on each load |
| Within-file time series, `chlor_a`, real bbox (lat 33-36, lon -123 to -120) | ✅ Correct dual-axis chart rendered (values + anomaly), series mean displayed |
| Batch time series, `chlor_a`, real bbox (lat 8-15, lon 82-90), date range 2026-01-01 to 2026-01-05 | ✅ Correct batch chart rendered against real MODIS batch directory, series mean displayed |
| Chart readability, both modes, after layout fix | ✅ X-axis labels angled and fully visible, no overlap/clipping, legend clear of tick labels |
| Existing `/stats` + raster query flow (regression check) | ✅ Unaffected — map, colormap, opacity, legend all continue working exactly as established through Day 24 |

## 5. Outcome
- Time-series charting (within-file and batch/directory modes) is fully implemented, Tauri-wired, and verified against both real MODIS swath data and the synthetic flat-grid fixture.
- Four bugs were found and fixed through direct interactive testing rather than assumed correct after a clean build — three were genuine state/reconciliation defects (not edge cases), and one was a presentation/layout issue reported directly by AKV via screenshots across iterative passes.
- A new bug category (React sibling-key collision) was identified and documented for the first time in this project, distinct from the previously recurring WSLg/sidecar/HDF5 patterns.
- No backend or sidecar changes were required this session — all four bugs and their fixes were confined to the frontend, so no PyInstaller rebuild was necessary.
- All Phase 3, Day 25 exit-criteria items met: charting library integrated, time-series anomaly trendlines rendering correctly in both required modes, verified live through the actual desktop UI.

## 6. Next Steps (Days 26-28)
Build auxiliary plots — histograms and scatter plots for parameter correlation — the next Phase 3 milestone item. Worth carrying forward Day 25's lesson before starting: any new sibling components added to the same parent that need file-change-triggered remounts should get distinctly namespaced `key` props from the start, rather than copy-pasting an existing key expression.