# Day 23 Summary Report — OC-ECV Local Engine

**Date:** August 12, 2026 (Phase 3, Day 23)
**Phase:** 3 — Visualization & Interactive UI Dashboards
**Status:** Complete — pixel-level raster rendering implemented end-to-end for both file structures, verified through the actual sidecar and live UI, zero regressions in the existing stats pipeline

## 1. Objective
Implement dynamic WebGL color-ramps (Viridis, Ocean, Jet) for scalar raster rendering — the first real use of `MapView`'s deck.gl layer stack for actual pixel data, extending Day 22's single bbox rectangle into genuine geospatial data visualization.

## 2. Design Decisions Made Before Implementation
Two forks were resolved deliberately before writing code, rather than discovered mid-implementation:

- **Flat-grid vs. swath rendering fork.** Flat-grid files have 1D, regularly-spaced lat/lon and map cleanly onto deck.gl's `BitmapLayer` (a simple corner-bounds image stretch). Real MODIS swath files have 2D, per-pixel, non-rectilinear lat/lon (satellite ground-track geometry) — `BitmapLayer` fundamentally doesn't apply. Chose to build both paths now: `BitmapLayer` for flat-grid, `ScatterplotLayer` (binary point data) for swath, rather than deferring or regridding.
- **Payload format.** Chose server-side encoding over JSON: flat-grid data as a grayscale+alpha PNG (luminance = normalized value, alpha = validity mask), swath data as packed binary `Float32Array`s. Colormaps are deliberately **not** baked in server-side — the backend sends raw normalized values, and the frontend applies Viridis/Ocean/Jet as a client-side lookup, so switching color ramps never requires a backend re-fetch.

## 3. Backend Work Completed

**Refactor (`backend/processing/statistics.py`) — verified zero-regression before building on it**
- Extracted the structure-detection/dispatch logic previously inline in `compute_regional_stats()` into a new shared `_get_subsetted_data()` function, with an optional `return_coords` parameter so `/stats` and the new `/raster` endpoint both reuse the exact same subsetting/masking pipeline instead of risking logic drift between two copies.
- Verified via `python -m processing.statistics` against the real MODIS granule and confirmed exact match against previously known-good values, then re-verified live through the UI on both file structures before proceeding.

**New Module (`backend/processing/raster.py`)**
- `encode_bitmap_png()` — grayscale+alpha PNG encoding for flat-grid data, with block-downsampling (nanmean-based) capping the longest side at 1024px given Day 16's 4000×5000 stress-test grids, and correct north-up row orientation handling based on the file's own lat ordering.
- `encode_points_binary()` — packed binary point encoding for swath data (`[uint32 count][float32 lon×N][float32 lat×N][float32 normalized_value×N]`), excluding NaN/masked pixels entirely rather than sending them transparent, with deterministic stride-based subsampling above a 500,000-point cap.
- `compute_regional_raster()` — main entrypoint, dispatches to the correct encoder based on `_get_subsetted_data()`'s reported structure type.

**New Endpoint (`backend/api/server.py`)**
- `/raster` — same query parameters as `/stats`; returns binary PNG or point data directly (not JSON-wrapped), with response metadata (value range, bounds, grid shape, point count) sent via custom headers (`X-Raster-Type`, `X-Value-Min/Max`, `X-Bounds`, `X-Grid-Shape`, `X-Point-Count`) to avoid a second round-trip.
- Added `expose_headers` to the existing CORS middleware — without it, `fetch()` silently returns `null` for all custom response headers despite the server sending them correctly, since browsers only expose a small default header allowlist otherwise. Caught and fixed proactively rather than as a follow-up debugging session.
- New dependency: Pillow (PNG encoding). Verified as pip-installable in isolation in `oc-ecv-env` (no `--break-system-packages` needed — that flag addresses a distro-Python protection that doesn't apply to conda environments, confirmed not needed here).

**Sidecar rebuild** — added `--collect-all PIL` to the PyInstaller build command, per Day 2's established precedent that C-extension packages need explicit collection flags; verified via the actual compiled binary (not just source) by hitting `/raster` directly in-browser while the sidecar was running.

## 4. Frontend Work Completed

**New Module (`frontend/src/utils/colormaps.ts`)**
- Hand-written RGB stop tables for Viridis, Ocean, and Jet, plus `getColor()` (linear interpolation lookup) and `recolorBitmap()` (canvas-based recoloring of the fetched grayscale+alpha PNG).

**`backendApi.ts`**
- `fetchRaster()` — branches on the `X-Raster-Type` response header; decodes PNG via `createImageBitmap()` for the bitmap path, or constructs three `Float32Array` views directly into the response `ArrayBuffer` at the byte offsets `raster.py` defines for the points path (relies on little-endian byte order matching between NumPy's `.tobytes()` and JS typed arrays on this project's x86_64 target — documented explicitly in code rather than left implicit).

**`MapView.tsx`**
- Added `BitmapLayer` (flat-grid, recolored canvas + bounds) and `ScatterplotLayer` (swath, binary attribute buffers for position/color) to the existing layer stack, alongside Day 22's bbox rectangle.
- Both the canvas recoloring and per-point color computation are wrapped in `useMemo` keyed on `[rasterResult, colormap]` — without this, every bbox keystroke (which re-renders `MapView` via `App`'s `mapBbox` state) would re-run potentially expensive recoloring even when neither the raster data nor colormap actually changed.

**`App.tsx`**
- New `rasterResult`/`rasterLoading`/`rasterError`/`colormap` state; `handleQuerySubmit` now fires `computeStats()` and `fetchRaster()` concurrently with independent error handling, so a raster failure (e.g. a genuinely empty region) doesn't block the stats panel from displaying, and vice versa.
- New colormap `<select>` control above the map. Deliberately minimal — opacity sliders and a value legend are Day 24's milestone item, not built here to avoid scope creep.

## 5. Testing Summary

| Test | Result |
|---|---|
| Source-level: `_get_subsetted_data()` refactor, real MODIS file | ✅ Exact match against pre-refactor known-good values (valid pixels, mean, min, max) |
| Source-level: `encode_bitmap_png()`, flat-grid synthetic file | ✅ PNG round-trip verified numerically (mode, size, valid-pixel count, full 0-255 luminance spread) |
| Source-level: `encode_points_binary()`, real MODIS file | ✅ `value_min`/`value_max`/`point_count` (67,299) exactly matched the already-verified `/stats` result for the same query |
| Sidecar: `/raster` via compiled binary, flat-grid | ✅ PNG served and rendered correctly in-browser; confirmed Pillow bundled correctly |
| UI: flat-grid raster + bbox rectangle, Run Query | ✅ Colored raster patch renders under the bbox rectangle (Viridis default) |
| UI: colormap switch, flat-grid (bitmap path) | ✅ Instant recolor, zero network activity confirmed via DevTools |
| UI: swath raster (real MODIS, `chlor_a`, bbox `[8,15,82,90]`) | ✅ Scattered colored points render, spatial pattern consistent with Day 8's known valid-data distribution for this file |
| UI: colormap switch, swath (points path) | ✅ Instant recolor confirmed (jet → viridis), same zero-refetch behavior as bitmap path |
| Console check across all above | ✅ Clean — one informational `deck: Attribute instanceFillColors is normalized` notice (confirms correct auto-detection of the Uint8Array color buffer, not an error; did not repeat per-frame) |

## 6. Outcome
- Both flat-grid (`BitmapLayer`) and swath (`ScatterplotLayer`) raster rendering paths are implemented, verified at the source level, cross-validated against already-proven `/stats` values, confirmed through the actual compiled sidecar (not just source), and tested live in the UI against real satellite data.
- Client-side colormap switching works identically and instantly on both rendering paths with zero backend re-fetch, confirming the "send raw values, colormap client-side" design decision paid off as intended.
- The `_get_subsetted_data()` refactor was verified as a genuinely zero-regression change before any new code was built on top of it, consistent with this project's established discipline for touching load-bearing shared logic.
- One CORS header-exposure gotcha was identified and fixed proactively (before it could manifest as a confusing "headers are always null" bug later), rather than discovered through debugging.
- All Phase 3, Day 23 exit-criteria items met: dynamic WebGL color-ramp rendering (Viridis/Ocean/Jet) implemented for scalar raster data, across both file structures this project supports.

## 7. Next Steps (Day 24)
Build map layer controls — opacity sliders and color scale legends. The value-range metadata (`X-Value-Min`/`X-Value-Max`) already flowing from `/raster` into `RasterResult` is directly reusable for the legend without any backend changes; opacity control will likely mean exposing a new prop through to the `BitmapLayer`/`ScatterplotLayer` `opacity` parameter already available in deck.gl.