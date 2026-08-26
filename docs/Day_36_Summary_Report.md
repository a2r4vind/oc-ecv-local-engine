# Day 36 Summary Report — OC-ECV Local Engine

**Date:** August 25, 2026 (Phase 4, Day 36)
**Phase:** 4 — Export Engines & Advanced Utilities
**Status:** Complete — high-res PNG/JPEG export implemented for both map and chart components; two real bugs found and fixed through live testing; all 7 planned tests passed

## 1. Objective
Implement high-resolution PNG/JPEG map and plot export functionality, per the milestone's Phase 4 opening item — the first Phase 4 feature and the first place this project exports visual output rather than raw data.

## 2. Work Completed

**Map Export (`frontend/src/utils/mapExport.ts`)**
- `exportMapToBlob()` — composites MapLibre's base canvas and deck.gl's overlay canvas (two separate `<canvas>` elements, per Day 22's overlaid `interleaved:false` decision) onto one offscreen canvas at a configurable resolution multiplier (default 2x), then encodes to PNG or JPEG.
- Required `canvasContextAttributes={{ preserveDrawingBuffer: true }}` on the MapLibre `<Map>` component — WebGL clears its drawing buffer after each frame by default, which would otherwise capture a blank buffer at the moment of export. Noted the maplibre-gl v5+ breaking change (`preserveDrawingBuffer` moved from a flat prop into a nested `canvasContextAttributes` object) directly in code comments to prevent a future regression.
- JPEG export flattens onto a white background first (JPEG has no alpha channel), avoiding transparent regions rendering as black in external viewers.

**Chart Export (`frontend/src/utils/chartExport.ts`)**
- `exportPlotToBlob()` — thin wrapper around `Plotly.toImage()`, used identically by `TimeSeriesChart`, `HistogramChart`, and `ScatterChart`.
- Must import from `"plotly.js-dist-min"`, not `"plotly.js"` — the latter pulls in Plotly's full trace registry (including the "image" trace), which bare-requires the unstyled Node `buffer/` polyfill package, breaking Vite's esbuild dependency scan project-wide. Documented explicitly in code comments as a do-not-reintroduce gotcha.

**Save Flow (`frontend/src/utils/saveFile.ts`, `components/ExportButton/`)**
- Native Tauri save dialog (`@tauri-apps/plugin-dialog`) + `@tauri-apps/plugin-fs` `writeFile`, shared by both export paths.
- Ran `npm run tauri add fs`, added explicit `fs:allow-write-file` scope to `capabilities/default.json` covering `$HOME/**`, `$DOWNLOAD/**`, `$DESKTOP/**`, `$DOCUMENT/**`.
- `ExportButton` wired into `MapView.tsx` (top-right overlay) and all three chart components.

## 3. Bugs Found and Fixed

| # | Bug | Root Cause | Resolution |
|---|---|---|---|
| 1 | Exported map PNGs correctly captured the MapLibre basemap and the bbox rectangle, but silently omitted the colored `BitmapLayer` raster patch — reproduced consistently, including when the raster had been fully rendered on-screen for an extended period beforehand (ruling out an async-timing race) | Diagnostic logging of `containerEl.querySelectorAll("canvas")` revealed **3** canvases present at export time, not the assumed 2: MapLibre's base canvas, a live deck.gl overlay canvas (correctly sized, `956×420`), and a second, orphaned `canvas id="deckgl-overlay"` stuck at the browser's uninitialized default size (`300×150`, no attributes ever set). `mapExport.ts`'s `.find((c) => c !== baseCanvas)` returned whichever non-base canvas came first in DOM order — the dead orphan, not the live one. Root cause of the orphan itself: `React.StrictMode` (confirmed present in `main.tsx`) double-invokes `DeckGLOverlay`'s `useControl` setup in dev, and the first `MapboxOverlay` instance's canvas is never cleaned up on the double-invoke's teardown. Dev-only — production builds don't double-invoke effects, so the orphan (and this exact failure mode) likely doesn't occur in a packaged build, though the export logic is now robust regardless |
| 2 | Exported Time Series chart PNGs/JPEGs showed a right-axis ("Anomaly") tick layout that didn't match the live chart — different tick values, inconsistent decimal places between ticks — with the "Anomaly" axis title visibly overlapping the tick labels | `Plotly.toImage()` renders into a separate, hidden/off-screen clone of the graph div rather than the live visible one. `yaxis` had no `automargin`, and `yaxis2` had neither `automargin` nor a fixed `tickformat` — only a static `margin.r: 50`. Text-measurement-dependent auto-margin/auto-tick logic behaved inconsistently against the hidden export clone, falling back to a plainer linear tick-spacing calculation with a too-narrow reserved margin for the actual rendered label widths | Added `automargin: true` to both `yaxis` and `yaxis2`, plus an explicit `tickformat: ".3f"` on `yaxis2` to remove the "nice round number vs. raw linear spacing" variability between live and export renders entirely, rather than only patching the margin symptom |

**Underlying lesson:** both bugs stemmed from the export path rendering into a context distinct from what's visibly on screen — an *extra*, hidden canvas in bug #1's case, and a hidden *clone* of the chart div in bug #2's case — rather than any error in the compositing/encoding logic itself. Neither was caught by watching the live app; both required inspecting the actual DOM/render state at the moment of export. Consistent with this project's established pattern (Day 25) that certain classes of bugs only surface through the actual rendering path, not source-level reasoning alone.

## 4. Testing Summary — All 7 Planned Tests

| # | Test | Result |
|---|---|---|
| 1 | Map export — flat-grid file, PNG (`sample_oceancolor.nc`, bbox lat 33-37/lon -124 to -119, `chlor_a`) | ✅ Base map + raster + bbox rectangle all present after fix; sharper than on-screen |
| 2 | Map export — swath file, points (real `AQUA_MODIS...L2.OC.nc`, bbox `[8,15,82,90]`, `chlor_a`) | ✅ Scattered colored points correctly composited from the deck.gl overlay canvas |
| 3 | Map export — JPEG | ✅ Solid white background, smaller file size than PNG |
| 4 | Chart export — Time Series, Histogram, Scatter, both PNG and JPEG | ✅ All traces/axes/legend intact after `yaxis`/`yaxis2` fix; Histogram's "Valid pixels/Mean/Std" caption text confirmed **not** baked into the image (only the Plotly div captured) |
| 5 | Cancel the native save dialog | ✅ No error shown, button returns to normal state, no crash/hang |
| 6 | Save inside `$HOME` (Desktop/Documents/project folder) | ✅ Succeeds cleanly |
| 7 | Save outside `$HOME` — WSL's Windows mount (`/mnt/c/Users/arvin/Documents`) | ✅ Genuinely uncertain case resolved to clean success — no crash, no frozen UI, file written correctly |

Secondary symptom noted in earlier testing (corrupted/garbled label glyph rendering in map exports, e.g. "Sacramento," "San Jose") was checked again after the canvas-selection fix and **no longer observed** — plausibly related to the same orphaned-canvas compositing issue, though not independently root-caused, so this is reported as an observation rather than a confirmed resolution.

## 5. Outcome
- High-resolution PNG/JPEG export is fully implemented and verified for both map (flat-grid raster, swath points, bbox overlay) and all three chart types, across both file structures this project supports.
- Two genuine bugs were found, root-caused via direct DOM/render-state inspection rather than assumed, and fixed — one in map canvas compositing, one in chart axis layout under Plotly's off-screen export render path.
- All export paths verified against the actual save flow, including the two edge cases most likely to fail silently (dialog cancellation, and a save path outside `$HOME` on the WSL/Windows boundary) — both resolved cleanly.
- One known, non-blocking follow-up carried forward: the underlying `useControl`/`MapboxOverlay` cleanup gap causing the StrictMode-orphaned canvas still exists — masked, not fixed, by the dimension-matching selection logic. Flagged for later cleanup if canvas count ever creeps further, not time-boxed into this session.
- All Phase 4, Day 36 exit-criteria items met: users can export high-res visual snapshots (map and chart) in both PNG and JPEG, verified against real data and real save-path edge cases.

## 6. Next Steps (Day 37)
Implement raw data matrix export (.bin, CSV tables) — the next Phase 4 milestone item, and the first Phase 4 export path operating on raw numeric data rather than rendered visual output.