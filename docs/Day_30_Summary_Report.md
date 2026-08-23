# Day 30 Summary Report — OC-ECV Local Engine

**Date:** August 19, 2026 (Phase 3, Day 30)
**Phase:** 3 — Visualization & Interactive UI Dashboards
**Status:** ✅ Complete — feature implemented, two blocking bugs found and fixed, full verification pass confirmed clean

---

## 1. Objective
Implement interactive tooltips on maps and charts for exact pixel value inspection — the final Week 5 milestone item, giving Giovanni-style hover feedback across both the raster map view (flat-grid and swath) and all three chart types (time series, histogram, scatter).

---

## 2. Work Completed

**`frontend/src/utils/colormaps.ts`**
- `decodeRawBitmapValues()` — decodes a flat-grid raster's grayscale+alpha PNG into a denormalized raw-value grid, independent of the display colormap (decoded once per raster result, not once per colormap switch).
- `lookupBitmapValue()` — resolves a raw value at a given map coordinate against the decoded grid and the raster's own geographic bounds; returns `null` for masked pixels or out-of-bounds coordinates.

**`frontend/src/components/MapView/MapView.tsx`**
- `getTooltip` callback wired into deck.gl's `MapboxOverlay`, handling the two structurally different layer types separately:
  - `ScatterplotLayer` (swath): exact per-point value, resolved by picked index against parallel typed arrays already in memory.
  - `BitmapLayer` (flat-grid): resolved via `lookupBitmapValue()` against the picked geographic coordinate.
- `pickable: true` added to both raster layers (required for deck.gl hover picking; previously unset/`false`).
- New `variable` prop threaded through from `App.tsx` for tooltip labeling.

**Chart tooltips** (`TimeSeriesChart.tsx`, `HistogramChart.tsx`, `ScatterChart.tsx`)
- Explicit `hovertemplate` added to all traces (previously relying on Plotly's untemplated defaults).
- `TimeSeriesChart`: `hovermode: "x unified"` groups both traces' tooltips into one box per x-position.
- `HistogramChart`: tooltip shows the full bin range, not just the bar center.

**Styling**
- `.deck-tooltip` styled in `MapView.css` using existing design tokens (`--oc-panel-bg`, `--oc-border`, IBM Plex Mono).

No backend changes were required — all raster endpoints already exposed the value range/bounds metadata needed for client-side denormalization.

---

## 3. Bugs Found and Fixed

Two related but distinct crashes were discovered during live testing, both stemming from `pickable: true` making the raster layers newly clickable — which surfaced pre-existing gaps in Phase C's `BboxDrawTool.ts` that had never been exercised before (Phase C's own testing covered *drawing* a rectangle, not clicking an *already-drawn* one).

### Bug 1 — Crash on click-to-select an existing rectangle
**Symptom:** Clicking inside an already-rendered bbox rectangle (with a raster visible) blanked the entire screen with `Error: No feature with id ..., can not delete`.

**Root cause:** `TerraDrawSelectMode`'s click-to-select handling fires terra-draw's `"change"` event for two reasons never previously distinguished: (a) genuine geometry changes, and (b) internal bookkeeping side effects — a `selected` property toggle, or creation of a selection-point helper feature (`selection-point.behavior.ts`). The existing `"change"` handler treated any change event's last-emitted ID as belonging to the rectangle, calling `emitFromFeatureId()` regardless. For helper-feature IDs, this incorrectly emitted `null` (looked like "bbox cleared"), which round-tripped through React state back into `MapView`'s bbox-sync effect, calling `setRectangle()` — re-entering terra-draw's raw store (`removeFeatures`/`addFeatures`) **while terra-draw's own click handler was still mid-execution on the call stack**, deleting a feature terra-draw's own suspended code still held a reference to.

**Fix:** `BboxDrawTool.ts` now explicitly tracks the rectangle's own feature ID (`rectangleFeatureId`), set on creation (`finish`, `setRectangle`) and cleared on removal. The `"change"` handler only reacts when the changed `ids` array actually includes this tracked ID — helper/selection-point feature changes are filtered out at the source and never reach `emit()`. A secondary defense-in-depth guard (skip `emit()` entirely if the resolved bbox is unchanged from `currentBboxState`, deferred via `queueMicrotask`) was also added.

### Bug 2 — Crash on editing a bbox field while the rectangle is selected
**Symptom:** After clicking a rectangle to select it (handles visible), editing a lat/lon numeric field blanked the screen with the same `"No feature with id..., can not delete"` error.

**Root cause:** A field edit flows `ParameterSelector` → `App.tsx` state → `bbox` prop → `MapView`'s sync effect → `setRectangle()`, which removes the old feature directly via the raw store API. `TerraDrawSelectMode` maintains its own internal "currently selected feature" reference separate from the store; removing the feature without deselecting it first orphans that internal reference, which later fails when the mode tries to act on it.

**Fix:** Added `deselectCurrent()`, calling terra-draw's public `deselectFeature(id)` (confirmed via the installed package's own `.d.ts` — initially assumed zero-argument, corrected after checking) against the tracked `rectangleFeatureId`, wrapped defensively since the call throws if the feature wasn't actually selected. Called at the start of both `setRectangle()` and `clear()`, before any raw store mutation.

**Verification for both:** Isolated via a `pickable: false` control test first (confirmed the crash was unrelated to Day 30's picking changes — it was a pre-existing Phase C gap, just newly reachable), then fixed and re-verified live: repeated click-to-select (3-4× in a row), field edits while selected, drawing a new rectangle over an old one, clearing, and tab/file switching — all clean after both fixes.

---

## 4. Flagged, Not Resolved — Backend Connectivity Event (Unreproduced)

During testing, one instance of `Failed to load resource: Connection terminated unexpectedly` occurred on `/stats` and `/raster` after several rapid successive queries against the same real MODIS file — the sidecar process was confirmed fully dead (`curl /health` failed to connect), not merely slow.

**Investigation:**
- `dmesg` showed no OOM-kill event.
- The launch terminal (`npm run tauri dev`) showed no Python traceback at the time of failure — consistent with either an external kill signal or a C-extension-level crash (e.g. HDF5/netCDF4/GDAL) below Python's ability to report it, rather than an unhandled Python exception.
- Running the compiled sidecar binary **directly** (bypassing Tauri's spawn mechanism) and repeating the same rapid-query pattern **11 consecutive times** (22 requests) produced zero failures — all `200 OK`.

**Status:** Not reproduced under direct-binary testing; the one concrete variable between the failing and clean runs is that the failure occurred through Tauri's spawned sidecar specifically. Time-boxed per this project's established practice (Day 21 precedent) rather than chased further this session — no backend code was touched today, and this is very unlikely to be a Day 30-introduced regression. Flagged as a follow-up: if it recurs, capture Tauri's own piped stdout/stderr at the moment of failure (not a directly-run binary, which bypasses the actual failure conditions).

---

## 5. Testing Summary

| Test | Result |
|---|---|
| Click-to-select rectangle, repeated 3-4× | ✅ No crash (post-fix) |
| Field edit while rectangle selected | ✅ No crash (post-fix) |
| Draw new rectangle over existing one | ✅ Clean |
| Clear rectangle | ✅ Clean |
| Tab switch / file switch | ✅ Clean |
| `pickable: false` isolation control | ✅ Confirmed bug was pre-existing, not caused by Day 30's picking changes |
| Backend connectivity event | ⚠️ Occurred once, unreproduced across 11 direct-binary trials — flagged, not resolved |
| Flat-grid hover — value + variable label | ✅ Confirmed |
| Masked/invalid pixel — no tooltip | ✅ Confirmed |
| Swath hover — value + lat/lon | ✅ Confirmed |
| Colormap-switch decoupling (value unchanged) | ✅ Confirmed |
| `.deck-tooltip` styling selector matches rendered DOM | ✅ Confirmed |
| Click-to-select + field-edit-while-selected, re-verified with `pickable: true` restored | ✅ Confirmed — both terra-draw fixes hold with picking active |
| Chart hovers — TimeSeries (`hovermode: x unified`), Histogram (bin range), Scatter (paired values) | ✅ Confirmed |

---

## 6. Outcome
Interactive tooltip functionality is implemented and fully verified across both map raster paths (flat-grid `BitmapLayer`, swath `ScatterplotLayer`) and all three chart types (time series, histogram, scatter). Two genuine, previously-undiscovered crash bugs in Phase C's `BboxDrawTool.ts` were found and fixed as a direct result of Day 30 making the raster layers pickable/clickable for the first time — both root-caused precisely (terra-draw internal state re-entrancy) rather than patched around symptomatically, and both verified via isolation testing (`pickable: false` control) before being attributed to Day 30 at all, then re-confirmed with `pickable: true` restored to ensure the fixes hold under the feature's actual shipped configuration. One unreproduced backend connectivity event was investigated, not resolved, and explicitly flagged as a follow-up rather than either ignored or allowed to block sign-off.

All Phase 3, Day 30 exit-criteria items met: interactive tooltips implemented on both maps and charts for exact pixel value inspection, verified live through the actual desktop UI rather than assumed correct after a clean build.

---

## 7. Next Steps
- Days 31-35: Integration & Stress Testing — connect visualization layers with backend processing outputs, optimize render speeds for large grids, per the original Phase 3 milestone plan.
- Carry forward: monitor for recurrence of the Section 4 backend connectivity event under normal (non-isolated) usage; if it recurs, capture Tauri's own piped stdout/stderr at the moment of failure rather than a directly-run binary.