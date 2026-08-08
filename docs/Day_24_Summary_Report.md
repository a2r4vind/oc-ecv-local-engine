# Day 24 Summary Report — OC-ECV Local Engine

**Date:** August 13, 2026 (Phase 3, Day 24)
**Phase:** 3 — Visualization & Interactive UI Dashboards
**Status:** Complete — opacity control and color-scale legend implemented, one native-widget rendering bug and one state-reference bug found and fixed, both verified through repeated live testing

## 1. Objective
Build map layer controls — opacity sliders and color-scale legends — giving the user control over how the Day 23 raster layer displays, and a labeled reference for interpreting its colors.

## 2. Design Decisions Made Before Implementation
- **Legend built from the same colormap stop tables as the raster itself** (`getGradientCss()` added to `colormaps.ts`), rather than a separately-defined gradient — guarantees the legend can never visually disagree with what's actually painted on the map, since both draw from one source of truth.
- **Opacity applied as a deck.gl layer-level `opacity` prop**, multiplying on top of each pixel/point's own validity-derived alpha (set in Day 23's encoding) rather than replacing it — masked/invalid data stays invisible at any opacity setting; the slider only affects how strongly *valid* data shows through the base map underneath.
- **Legend as a static bar above the map** (not overlaid on the map canvas) — deliberately deferred a more GIS-native overlaid look to Day 29's "professional NASA Giovanni styling" milestone, to avoid conflating layout polish with this day's functional scope.

## 3. Work Completed

**`colormaps.ts`**
- `getGradientCss()` — converts an existing colormap's stop table into a CSS `linear-gradient()` string, reusing the same data the raster recoloring uses.

**New Component (`frontend/src/components/ColorLegend/ColorLegend.tsx` + `.css`)**
- Renders the variable name, a gradient bar, and min/max value labels, sourced entirely from `RasterResult`'s existing `valueMin`/`valueMax` (no new backend data needed) and the currently-queried variable name.

**New Component (`frontend/src/components/OpacitySlider/OpacitySlider.tsx` + `.css`)**
- Fully custom pointer-driven slider (drag, click-to-jump, and arrow-key support), built from plain `<div>`s rather than a native `<input type="range">`.

**`MapView.tsx` / `App.tsx`**
- New `opacity` prop threaded through to both `BitmapLayer` and `ScatterplotLayer`.
- New `opacity`/`colormap` state deliberately **not** reset on file switch — treated as persistent display preferences, consistent with `mapBbox`/`statsResult`/`rasterResult` being query-specific results that *do* reset. Confirmed as a deliberate choice, not an oversight, after direct evaluation of both options.

## 4. Bugs Found and Fixed

| # | Bug | Root Cause | Resolution |
|---|---|---|---|
| 1 | Opacity slider thumb sat visibly inset from the track edges at 0%/100%, and CSS overrides (`-webkit-appearance: none`, custom thumb styling) had no visible effect at all | Native `<input type="range">` rendering under WSLg's WebKitGTK webview — Computed styles confirmed `appearance: auto` even with the override rule present, meaning the CSS genuinely wasn't being honored. Same root-cause category as Day 12-14's native date-picker freeze: native OS-level form widgets misbehaving specifically in this environment | Replaced the native range input entirely with a custom pointer-driven `<div>`-based `OpacitySlider` component — same fix pattern as `DatePickerField`. Verified via inspector that the earlier native-widget approach truly wasn't styleable here before committing to the rewrite, rather than guessing |
| 2 | Dragging the opacity slider (or any unrelated UI change) silently reset the map's pan/zoom back to the file's full auto-fit extent, discarding manual navigation | `spatialBounds` in `App.tsx` was a fresh object literal computed on every render. `MapView`'s auto-zoom `useEffect` is keyed on `[spatialBounds]`, and React's dependency comparison is reference-based — a new object reference (even with byte-identical lat/lon values) re-triggered `fitBounds()` on every re-render, not just genuine file changes. Present in principle since Day 22 (any bbox keystroke had the same effect) but not noticed until opacity dragging made a deliberately-zoomed view visibly snap back | Wrapped `spatialBounds` in `useMemo(..., [ingestedResult])`, so its reference only changes when a file is actually (re-)ingested, not on unrelated state updates |

## 5. Testing Summary

| Test | Result |
|---|---|
| Drag slider to intermediate values | ✅ Fill/thumb track smoothly; raster opacity visibly changes in between, not just at extremes |
| Click directly on track (no drag) | ✅ Jumps immediately to the clicked position |
| Keyboard (←/→ after focus) | ✅ Nudges opacity by 1% per press |
| Low opacity vs. masked pixels | ✅ Valid data fades correctly; masked/invalid pixels remain fully invisible throughout, confirming opacity multiplies on top of (not replaces) validity alpha |
| Manual pan/zoom survives opacity drag (post-fix) | ✅ Map holds position; no longer snaps back to file extent on unrelated state changes |
| Opacity/colormap across file switch | ✅ Persist as intended (confirmed as deliberate design choice, not a defect) |
| Legend gradient matches map colors, across all three colormaps | ✅ Visually consistent, since both draw from the same stop tables |
| Legend bar width/label separation | ✅ Full-width bar (640px), min/max labels clearly separated at each end |

## 6. Outcome
- Opacity control and color-scale legend are both implemented and working correctly across drag, click, and keyboard interaction, verified against both flat-grid and swath raster types.
- Two real bugs were found and fixed during implementation, not just the originally-scoped features: a native-widget rendering failure (second occurrence of this project's known WSLg/WebKitGTK pattern) and a stale-reference re-render bug that silently discarded user navigation.
- The native-widget bug was root-caused via direct inspector verification (`appearance: auto` in Computed styles) before committing to a full component rewrite, rather than assumed or guessed at.
- The re-render bug's fix (`useMemo` on `spatialBounds`) closes a latent issue that had technically existed since Day 22, surfaced only now because Day 24 was the first feature to make its effect visually obvious.
- All Phase 3, Day 24 exit-criteria items met: map layer controls (opacity sliders, color scale legends) built and verified.

## 7. Next Steps (Day 25)
Integrate a charting library (Chart.js / Plotly.js) for time-series anomaly trendlines — the next Phase 3 milestone item, and the first place this project's flat-grid multi-time-step data (previously only ever squeezed down to a single snapshot for raster rendering, per Day 23's `values[0]` simplification) will be visualized across its full time dimension rather than one slice at a time.