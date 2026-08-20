# Day 29 Extra work Phases C Summary Report — OC-ECV Local Engine

**Date:** August 13–19, 2026 (Phase C, extra-scope work beyond Day 29's milestone)
**Phase:** 3 — Visualization & Interactive UI Dashboards (Giovanni-style rebuild, Phase C of 4)
**Status:** Partially complete — graticule with N/S/E/W labels fully shipped; interactive bbox drawing implemented and functionally correct but **deferred** due to an unresolved WSLg/WebKitGTK rendering-pipeline limitation

## 1. Objective
Replicate NASA Giovanni's region-selection UX: a collapsed bbox text input with a map-icon toggle, an interactive map with a draw/pan/zoom toolbar (single-tool state machine, yellow active-tool highlight), two-way sync between drawn rectangles and the four numeric lat/lon fields, and a toggleable lat/lon graticule overlay — building on Phase A (sidebar+persistent-map shell) and Phase B (icon/date-range polish).

## 2. Library Investigation (resolved before implementation, per established Day 22 discipline)
- **`@mapbox/mapbox-gl-draw`** — rejected. Only compatible with MapLibre via an unofficial pre-fork surface; requires manually overriding internal CSS class constants. Same version-skew risk category as Day 22's deck.gl/MapLibre incident.
- **`terra-draw` + `terra-draw-maplibre-gl-adapter`** — selected. MapLibre-native, actively maintained, ships a purpose-built `TerraDrawRectangleMode`. Used at the low level (`TerraDraw` + adapter + mode classes) rather than its prebuilt UI control, since a custom toolbar/state-machine was required.
- **Graticule** — built custom (GeoJSON line + symbol layers recomputed from `map.getBounds()` on `moveend`) rather than adding a dedicated plugin dependency; simple enough to own directly.

## 3. Work Completed

**`BboxDrawTool.ts`** (new) — wraps a single `TerraDraw` instance per `<MapView>` mount, exposing a bbox-oriented API (`startDraw`/`stopDraw`/`setRectangle`/`getRectangle`/`onBboxChange`) rather than terra-draw's general drawing surface. "Pan" state uses `TerraDrawSelectMode` with all edit flags disabled (renders existing rectangle read-only) rather than a "static" mode, since the latter couldn't be verified in terra-draw's public API.

**`MapToolbar.tsx` / `.css`** (new) — presentational-only toolbar (draw/pan toggle, zoom in/out, 4 arrow-pan buttons, graticule toggle). Owns no state; `MapView.tsx` is the single source of truth for `activeTool`/`graticuleOn`, so the toolbar's highlight can never drift from the map's actual behavior. Inline SVG icons throughout (no emoji, per established WebKitGTK tofu-box precedent).

**`Graticule.ts`** (new) — pure GeoJSON generation (`buildGraticuleGeoJSON`, `buildGraticuleLabelsGeoJSON`), "nice" step-size selection (1/2/5×10ⁿ) targeting ~4–10 lines across the current view span. Label layer added after initial user feedback that plain grid lines without N/S/E/W values weren't sufficient — labels placed along the left/top edges per Giovanni's own convention.

**`MapView.tsx`** — substantial rewrite: instantiates `BboxDrawTool` post-`onLoad` gate (same discipline as existing `fitBounds`/`resize` calls), owns `activeTool`/`graticuleOn` state, toggles **all** MapLibre camera-interaction handlers (not just `dragPan`) during draw mode, wires zoom/pan-arrow buttons directly to MapLibre methods. The Day 22–24 deck.gl `PolygonLayer` bbox rectangle was removed — terra-draw is now the single rendering source for the rectangle, avoiding a duplicate/non-interactive overlay.

**Option A bbox lifting** — `ParameterSelector.tsx`, `TimeSeriesPanel.tsx`, `HistogramPanel.tsx`, `ScatterPanel.tsx` all gained a new `bbox` prop and a sync `useEffect`, closing a real one-way-only gap: all four panels previously only *emitted* bbox changes upward (typed-field → state), with no path for an externally-changed bbox (a map-drawn rectangle) to flow back down into the visible fields. Each panel retains local string state for smooth typing, guarded against re-syncing a value it just emitted itself (`lastEmittedRef` + `bboxRoughlyEqual`) to avoid fighting the user's keystrokes.

## 4. Bugs Found and Fixed

| # | Bug | Root Cause | Resolution |
|---|---|---|---|
| 1 | Trackpad drag panned the map instead of drawing, even in draw mode | Only `dragPan` was disabled; trackpad gestures under WSLg can be picked up by `touchZoomRotate`/other handlers instead | Disabled all camera-interaction handlers (`dragPan`, `scrollZoom`, `boxZoom`, `dragRotate`, `doubleClickZoom`, `touchZoomRotate`, `touchPitch`, `keyboard`) during draw mode; re-enabled on exit |
| 2 | Graticule initially had no degree labels | Lines-only implementation; user expected Giovanni-style N/S/E/W labeled grid | Added a `symbol` layer (`buildGraticuleLabelsGeoJSON`) alongside the existing `line` layer, sharing the same step-size logic |
| 3 | `TimeSeriesPanel.tsx` had 2 pre-existing type errors (`file_name`/`variable`/`file_count` optionality mismatch between `backendApi.ts` and `timeseries.ts`) | Unrelated to Phase C; first surfaced only because `tsc --noEmit` was run standalone for the first time this session | Widened `timeseries.ts`'s local `WithinFileResult`/`BatchTimeseriesResult` interfaces to match `backendApi.ts`'s actual optional fields (neither field is read by the normalizer functions) |
| 4 | Rectangle drawing worked exactly once per session, then permanently produced zero-area boxes until a full file reload | `MapView`'s bbox-sync effect calls `setRectangle()` after every successful draw (round-trip through `App.tsx`); `setRectangle()` unconditionally deleted + re-added the feature via the raw store API even when the value hadn't changed, corrupting `TerraDrawRectangleMode`'s internal state after the first invocation | Added a `bboxEqual` guard in `setRectangle()` — no-ops when the incoming value already matches what's on the map; destructive remove+re-add now only fires on a genuinely different value |
| 5 | `TerraDrawRectangleMode`'s interaction pattern was left on the library's unstated default, producing zero-area boxes from quick trackpad taps | terra-draw supports 3 distinct `drawInteraction` modes (`click-drag`, `click-move`, `click-move-or-drag`); none was explicitly set | Explicitly set `drawInteraction: "click-move-or-drag"` to accept both gesture styles |

## 5. Known, Unresolved Limitation (Deferred)

**Symptom:** During active rectangle drawing, the live preview rectangle intermittently freezes/stutters mid-gesture (whether click-move-click or press-drag-release) instead of tracking the cursor continuously. When it does freeze, the subsequent finishing click/release produces either a degenerate near-zero-area box or no visible rectangle at all.

**Investigated and ruled out:**
- MapLibre's implicit repaint-on-`setData()` not firing reliably — addressed via explicit `map.triggerRepaint()` forced on every terra-draw `change`/`finish` event.
- Live preview using a separate internal render path bypassing terra-draw's public events entirely — addressed via a blunt backstop forcing `triggerRepaint()` on every raw `pointermove`/`mousemove`/`touchmove` while draw mode is active.
- Session-persistent state corruption from the sync-effect's `setRectangle()` calls — found and fixed (bug #4 above); this materially reduced but did not eliminate the stuttering.
- An `as any`-typed defensive coordinate-extraction path (introduced via external troubleshooting mid-session) was reviewed and found to be a functional no-op masking, not fixing, an unidentified issue — removed.

**Current assessment:** the residual stuttering most likely sits in the WSLg/WebKitGTK software-rendering pipeline itself — consistent with this project's established pattern of native-widget and rendering-timing issues specific to this environment (Day 12-14's date-picker freeze, Day 22's `map.transform` race, Day 24's opacity-slider `appearance` override) — rather than in application-level event wiring, which has now been hardened through several independent layers (explicit repaint triggers, camera-handler lockout, single-rectangle enforcement, sync-loop prevention) without resolving the core symptom.

**Interim state:** numeric lat/lon field entry remains the fully functional, verified primary bbox-input path across all four panels (Query/Time Series/Histogram/Scatter), consistent with the project's established deferral pattern (Day 21 Sea Ice Concentration). Interactive map-drawing is implemented and architecturally sound but not release-ready pending either (a) testing on a native Linux target or with a physical mouse to isolate whether this is WSLg/trackpad-specific, or (b) further investigation time not currently justified against the Sept 15 deadline.

## 6. Outcome
- Graticule with degree labels: **shipped, verified working** (toggle on/off, correct spacing across zoom levels, N/S/E/W formatting).
- Toolbar state machine (exclusive draw/pan, always-available zoom/pan-arrow buttons): **shipped, verified working**.
- Tab-independent bbox model (Option A): **verified working** — each of the 4 panels' bbox state confirmed fully isolated from the others across tab switches.
- Numeric field ↔ map two-way sync: **verified working** for the numeric-fields-drive-map direction; map-drives-numeric-fields direction works when a rectangle successfully finishes, but is gated by the deferred drawing-reliability issue above.
- Interactive bbox drawing (click-based or drag-based rectangle creation): **implemented, deferred** — not considered done for release purposes.
- Five real bugs found and fixed during implementation (table above), each independently verified rather than assumed.

## 7. Next Steps
Move to **Phase D** (batch-mode/multi-file directory valid date-range scanning — stretch scope, not yet started) and **Day 30** milestone tasks (interactive tooltips on maps/charts for exact pixel value inspection), per the original 8-week plan, to stay on track for the September 15, 2026 MVP deadline. Revisit the interactive-bbox-drawing stutter only if time permits later in the schedule, or if it can be cheaply retested on a non-WSL environment.