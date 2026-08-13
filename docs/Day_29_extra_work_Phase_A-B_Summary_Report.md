# Day 29 Extra work Phases A-B Summary Report — OC-ECV Local Engine

**Date:** August 18-19, 2026 (Extra Scope — beyond Phase 3, Day 29 milestone)
**Phase:** 3 — Visualization & Interactive UI Dashboards (Giovanni-style structural rebuild, Phases A-B of a 4-phase extra-scope plan)
**Status:** Complete — sidebar/persistent-map layout shell rebuilt, multiple real layout regressions found and fixed, date-range UX polish delivered; all changes user-tested and verified

## 1. Objective
Following Day 29's milestone-scoped visual/typography pass, AKV requested a full structural rebuild of the UI to match NASA Giovanni's actual interaction model — a left-side collapsible parameter panel with a persistent map/results area on the right, rather than the existing stacked-vertical-sections layout. Scoped and sequenced as four phases (A: layout shell, B: date-range polish, C: interactive bbox drawing + grid lines, D: batch-mode date-range scanning — deferred). This report covers Phases A and B, both completed and verified this block.

## 2. Scope Decision
This work sits outside the milestone document's Day 29 item ("refine UI styling to mimic professional NASA Giovanni layouts," already delivered and reported separately) — it was explicitly requested and accepted by AKV as additional work eating into project buffer time, ahead of the September 15 deadline, rather than being part of the original day-by-day plan. Tracked separately from milestone-day reports for that reason.

## 3. Phase A — Layout Shell

**Architecture delivered**
- `App.tsx` restructured as the shell owner: full-width collapsible `FileUploader` (compact `.loaded-file-bar` once a file loads, with a proper reset-to-null "Change file" flow, not a placeholder) sits above a two-region `.app-shell` — a fixed-width `.sidebar` with four mode tabs (Query / Time Series / Histogram / Scatter) and a persistent `.main-area` holding the map, colormap/opacity controls, and a results area that switches content by active mode.
- All four sidebar panels (`ParameterSelector`, `TimeSeriesPanel`, `HistogramPanel`, `ScatterPanel`) converted from self-contained (own result rendering) to reporting-upward via an `onResult` callback, so results always render in the persistent `.main-area` rather than inside whichever sidebar panel happens to be active.
- **Bbox architecture (Option A, confirmed with AKV after testing both options):** each of the four panels owns its own independent bounding-box state; typing in one panel's bbox fields never affects another's, and each survives switching away and back to that tab. Implemented by keeping all four panels permanently mounted (visibility toggled via CSS `display:none`, not conditional unmount/remount) — critical, since unmounting was the original cause of bbox values resetting on tab switch.
- Raster/colormap/legend display restricted to the Query tab only — other tabs show the base map and their own tab's bbox rectangle, avoiding a stale, wrong-variable raster bleeding across modes.

**Bugs found and fixed during Phase A** (all discovered through live testing, several requiring multiple iterations):

| # | Bug | Root cause | Resolution |
|---|---|---|---|
| 1 | Bbox values silently reset when switching tabs; Query tab's bbox appeared to "leak" into other tabs | Panels were conditionally unmounted on tab switch, wiping `useState`; a single shared `mapBbox` was read by all panels as initial state | Converted to always-mounted + CSS-hidden panels; replaced single shared bbox with per-mode `bboxByMode` record |
| 2 | Map/raster from Query tab stayed visible (wrong variable, wrong bbox) when switching to Time Series/Histogram/Scatter | `rasterResult` was a single global value only ever set by the Query flow, rendered unconditionally regardless of active tab | Raster/legend/colormap controls now gated on `activeMode === "stats"` |
| 3 | Map failed to render/auto-zoom on file load, intermittently — sometimes required running a query first to "fix" itself | `fitBounds()`/`resize()` were called before MapLibre's internal GL context/style had actually finished initializing (before `onLoad`) — a known source of silent, timing-dependent no-ops | Gated all `mapRef.current.*` calls behind MapLibre's `onLoad` callback via a `mapLoaded` state, with a double-`requestAnimationFrame` wait for a settled first paint |
| 4 | `.main-area` (map/results column) collapsed to ~2px wide on initial paint across every non-Query tab; self-corrected only after Plotly injected a chart | This WebKitGTK/WSLg build's flexible-track-sizing computation is unreliable on first paint — confirmed after `flex:1`, CSS Grid `1fr`, and `calc(100% - Npx)` all failed identically | Resolved (found by AKV's sister) via an oversized absolute unit (`width: 100em`) on `.main-area`, relying on the flex container's own overflow to clip it back down — sidesteps the faulty relative-sizing computation entirely. Documented as a recurring bug class for this environment. |
| 5 | Sidebar's own width also became unstable/overflowed while chasing bug #4 (two-column bbox grid pushing wider than the sidebar's declared width) | Grid track sizing (`minmax(0,...)`) alone didn't prevent content-driven overflow once combined with bug #4's symptoms | Stacked bbox/date-range fields to one column inside the sidebar (`grid-template-columns: 1fr` override), removing the pressure entirely |

## 4. Phase B — Date Range Polish

- **Calendar icon:** replaced the 📅 emoji toggle button with an inline SVG calendar icon in `DatePickerField`. Root-caused the emoji rendering as a broken "tofu" box specifically to this WebKitGTK build lacking emoji/color-glyph support — not a sizing or z-index issue. Same fix applied proactively to the file-bar's 📄 icon before it could cause the same problem.
- **Within-file valid date-range display:** added a "Valid range: [min] to [max]" note beneath the Date Range fields in both `ParameterSelector` (Query tab) and `TimeSeriesPanel` ("within this file" mode only), sourced entirely from `IngestionResult.metadata.time_steps` already returned by `/ingest` — no new backend endpoint or call needed. Deliberately scoped to within-file mode only; batch/directory-mode range scanning requires a new backend function and is deferred to Phase D.

## 5. Testing Summary

All testing performed live through the actual desktop app across multiple iterations, consistent with this project's established verification standard for UI-facing work.

| Test | Result |
|---|---|
| Mode tab switching, all four tabs | ✅ Each panel's bbox independently persists; no cross-tab leakage |
| Map bbox rectangle reflects active tab only | ✅ Verified across all four tabs |
| Raster/legend/colormap controls | ✅ Query-only, confirmed absent and non-stale on other tabs |
| Map render/auto-zoom on fresh file load (no prior interaction) | ✅ Consistent across repeated file-switch cycles, previously intermittent |
| `.main-area` sizing on direct tab load (no prior interaction) | ✅ Correct immediately on all four tabs, previously collapsed |
| Bbox/date fields fully visible, not clipped, in sidebar width | ✅ Confirmed after single-column stacking fix |
| Change-file flow | ✅ Returns cleanly to full uploader, no placeholder artifacts |
| Calendar icon rendering | ✅ Renders as proper icon in both Query and Time Series date fields |
| File icon rendering | ✅ Renders correctly in loaded-file-bar |
| Valid date-range note — flat-grid file, within-file mode | ✅ Correct real min/max dates shown |
| Valid date-range note — swath file (no time dimension) | ✅ Correctly absent, no crash |
| Valid date-range note — batch mode | ✅ Correctly absent (deferred to Phase D), no crash |

## 6. Outcome
- Phase A's sidebar/persistent-map shell is fully implemented, matching Giovanni's core interaction model, with the per-panel bbox architecture (Option A) deliberately chosen and confirmed by AKV after evaluating both the isolated and shared-state approaches directly against live behavior.
- Five distinct, real layout/rendering bugs were found and fixed during Phase A — three attributable to this project's now well-established WSLg/WebKitGTK rendering-quirk pattern (native/engine-specific behavior diverging from mainstream browsers), consistent with the date-picker, opacity-slider, and map-canvas issues from earlier phases.
- A new, generalizable bug class for this project was identified and documented: WebKitGTK's flexible-track-sizing computation (flex, grid, and calc-based sizing alike) is unreliable on initial paint in this environment — the oversized-absolute-unit workaround is now recorded for immediate reuse if this recurs elsewhere in the app.
- Phase B delivered both its planned items (calendar icon, valid-range display) plus a proactive fix (file icon) for the same underlying emoji-rendering gap, avoiding a near-certain repeat bug report.
- No backend changes were required in either phase — all work was frontend/CSS/React, so no sidecar rebuild was needed at any point.

## 7. Next Steps (Phase C)
Interactive, Giovanni-style bbox drawing on the map (draw/pan tool toggle with active-tool highlighting, zoom/pan button cluster, bidirectional sync between drawn rectangle and the existing numeric bbox fields) plus a toggleable lat/lon grid-line overlay, bundled into the same phase since both touch `MapView.tsx`. Per AKV's own precedent from Day 22, this requires a short library investigation (evaluating `mapbox-gl-draw`'s MapLibre compatibility, `@deck.gl/layers`' `EditableGeoJsonLayer`, or a fully custom pointer-driven implementation matching this project's established pattern of replacing problematic native/third-party widgets) before any implementation begins, to avoid a repeat of Day 22's mid-build architecture pivot.