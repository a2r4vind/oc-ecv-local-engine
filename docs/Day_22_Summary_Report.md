# Day 22 Summary Report — OC-ECV Local Engine

**Date:** August 11, 2026 (Phase 3, Day 22)
**Phase:** 3 — Visualization & Interactive UI Dashboards
**Status:** Complete — base map integrated and verified across both file structures; two real library-compatibility bugs found and fixed; one architecture pivot made before implementation began

## 1. Objective
Integrate Leaflet.js / Deck.gl into the React frontend, per the milestone's Phase 3 opening item — establishing the interactive map component that Day 23+ will extend with WebGL color-ramped raster rendering.

## 2. Architecture Decision: MapLibre GL + deck.gl (Interleaved→Overlaid), not Leaflet
The milestone doc names "Leaflet.js / Deck.gl" as one combined item; before writing any code, this was resolved into a concrete stack rather than assumed:
- Investigated pairing deck.gl with Leaflet directly. Found deck.gl has no official Leaflet integration module — only third-party/community options exist, and the deck.gl team explicitly discourages combining deck.gl with Leaflet for performance-heavy use cases (relevant here, since Day 23's raster layer is exactly that use case).
- Pivoted to deck.gl's officially recommended path instead: **MapLibre GL JS** as the base map, with deck.gl in interleaved single-canvas mode via `@deck.gl/mapbox`'s `MapboxOverlay` (works with MapLibre despite the package name).
- Installed `maplibre-gl`, `react-map-gl`, `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/mapbox`; uninstalled `leaflet`/`react-leaflet`/`@types/leaflet`, which had been installed under the original (incorrect) assumption before this investigation.

## 3. Work Completed

**New Component (`frontend/src/components/MapView/MapView.tsx` + `MapView.css`)**
- Renders a MapLibre GL map (CARTO Positron basemap style, no API key required) with a deck.gl `PolygonLayer` overlay showing the current query bounding box as a semi-transparent blue rectangle.
- Auto-fits the map view to the ingested file's own spatial extent (`lat_range`/`lon_range` from `IngestionResult.metadata`) whenever a new file loads, via MapLibre's `fitBounds()`.
- Sized and centered to match the app's existing ~640px content column rather than spanning the full window width.

**State Wiring (`App.tsx`, `ParameterSelector.tsx`)**
- Rather than fully lifting the four bbox inputs into controlled props (larger refactor), `ParameterSelector` keeps its existing local state and additionally reports changes upward via a new optional `onBboxChange` callback, feeding a new `mapBbox` state in `App.tsx` that `MapView` reads for the overlay rectangle.
- `mapBbox` resets to `null` on every new file ingestion, preventing a stale rectangle from a previous file lingering after a file switch.
- Two-way editing (dragging on the map to set the bbox) was scoped out of Day 22 as a deliberate deferral, not a gap — natural to revisit once Day 23's raster layer work is already touching this component.

## 4. Bugs Found and Fixed

| # | Bug | Root Cause | Resolution |
|---|---|---|---|
| 1 | MapLibre worker 404, cascading into `map.transform.height` TypeErrors in both MapLibre's own render loop and deck.gl's per-frame viewport sync | `maplibre-gl@6.1.0` ships ESM-only and requires the worker URL wired explicitly under Vite — it no longer auto-resolves (v5→v6 breaking change) | Added explicit `setWorkerUrl()` call using a `?worker&url` Vite import of `maplibre-gl-worker.mjs` |
| 2 | Same `map.transform.height` TypeError recurring continuously (100+ times) even after bug #1's fix, whenever bbox inputs changed; deck.gl layer never rendered | Interleaved mode (`MapboxOverlay({ interleaved: true })`) reads MapLibre's internal `transform` object every frame to sync cameras; version skew between `@deck.gl/mapbox@9.3.7` and the very recent `maplibre-gl@6.1.0` broke that internal assumption. Interleaved mode also requires a `beforeId` prop per layer (absent), compounding the issue | Switched to overlaid mode (`interleaved: false`) — deck.gl renders into its own separate canvas rather than reading MapLibre's internals per-frame, avoiding both the version-skew crash and the missing-`beforeId` requirement |

Two smaller manual-editing slips were also caught and fixed during implementation: a missing closing brace in one of `ParameterSelector`'s bbox `onChange` handlers (syntax error, caught immediately by Vite), and a missing `align-self: center` on `.map-view` under the app's flex container (map rendered full-width/left-aligned instead of matching the app's centered content column).

## 5. Testing Summary

| Test | Result |
|---|---|
| Auto-zoom on file load — `sample_oceancolor.nc` (flat-grid, California coast) | ✅ Correctly fits to `lat 32-38, lon -125 to -118` |
| Auto-zoom on file load — real `AQUA_MODIS...L2.OC.nc` (grouped-swath, Bay of Bengal) | ✅ Correctly fits to `lat 4.26-25.28, lon 69.45-94.58` |
| Live bbox rectangle — valid, in-view bbox on both file types | ✅ Rectangle renders and updates live as fields change |
| End-to-end: bbox rectangle → Run Query → real `/stats` result | ✅ Real MODIS granule, `chlor_a`, bbox `[8,15,82,90]` (Bay of Bengal): 9.7% valid fraction, mean 0.2804 — consistent with Day 8's prior findings for this region |
| File switch mid-session (no app restart) | ✅ Old rectangle clears, map re-fits to new file, new rectangle draws correctly |
| Partial/invalid bbox (empty fields) | ✅ No rectangle drawn; clearing a field after a valid box cleanly removes the rectangle |
| Numerically-valid but geographically out-of-view bbox (`lon -20 to -10` against a California-zoomed map) | ✅ Correctly decoupled: rectangle layer is added (per `isValidBbox()`'s purely numeric check) but renders off-screen since the map doesn't re-pan to query bboxes; backend correctly rejects it as non-overlapping on Run Query. Confirms map display and backend geographic validation are intentionally independent checks, not a single shared one |
| Window resize | ✅ Map canvas resizes cleanly with the window |

## 6. Outcome
- MapLibre GL + deck.gl base map is integrated, verified against both file structures (flat-grid and grouped-swath) established since Phase 1, and confirmed compatible with the existing `/stats` query pipeline end-to-end.
- Two genuine library-compatibility bugs were found and fixed, both stemming from pairing very recent major versions of `maplibre-gl` and `@deck.gl/mapbox` — neither was assumed away or worked around superficially; both were root-caused (worker URL resolution, then interleaved-mode camera sync) before being fixed.
- An initial architecture assumption (`@deck.gl/leaflet`) was caught and corrected *before* implementation began, avoiding wasted build effort — consistent with this project's established "verify before trusting" discipline, applied here to a dependency/architecture choice rather than a data-processing result.
- Known limitation, not a defect: the map does not auto-pan to an arbitrary typed bbox, only to the file's own extent on load — flagged as a possible Day 23+ polish item rather than addressed now.
- Follow-up flagged for Day 23 planning: since overlaid (not interleaved) mode was ultimately used, worth watching whether deck.gl's separate-canvas approach holds up once Day 23 adds a substantially larger, more performance-sensitive WebGL raster layer — may need to revisit interleaved mode (with the `beforeId` requirement now known) if overlaid mode doesn't scale.
- All Phase 3, Day 22 exit-criteria items met: Leaflet/Deck.gl (resolved to MapLibre + deck.gl) integrated into the React frontend, tested and verified rather than assumed working from a clean build.

## 7. Next Steps (Day 23)
Implement dynamic WebGL color-ramps (Viridis, Ocean, Jet) for scalar raster rendering — the first real use of `MapView`'s deck.gl layer stack for actual pixel data rather than a single bbox rectangle, and the point at which today's overlaid-vs-interleaved mode choice will be performance-tested under real load.