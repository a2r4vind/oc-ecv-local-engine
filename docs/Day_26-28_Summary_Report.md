# Day 26-28 Summary Report — OC-ECV Local Engine

**Date:** August 15-17, 2026 (Phase 3, Days 26-28)
**Phase:** 3 — Visualization & Interactive UI Dashboards
**Status:** Complete — histograms and scatter plots implemented end-to-end, verified against real satellite data at the source level, through the compiled sidecar, and live in the desktop UI; zero bugs found this block

## 1. Objective
Build auxiliary plots — histograms and scatter plots for parameter correlation — the next Phase 3 milestone item, following directly on from Day 25's time-series charting. Per this project's established Day 23 discipline: backend endpoints built and verified (source, then sidecar) before any frontend work begins.

## 2. Design Decisions Made Before Implementation
- **Histogram binning happens backend-side** (`numpy.histogram`), sending only bin edges + counts rather than raw pixel arrays — consistent with Day 23's "don't ship raw arrays without reason" principle already established for raster encoding.
- **Scatter pairing:** two variables subsetted independently via the shared `_get_subsetted_data()` (Day 23) using identical bbox/date/quality-flag parameters. Since both calls crop against the same file's same geometry, array shapes line up 1:1 without extra alignment logic — verified defensively with an explicit shape check rather than assumed. Pixels invalid in *either* variable are excluded, since a correlation point needs both values.
- **Scatter point cap:** reused Day 23's exact 500,000-point, stride-based (not random) subsampling convention from `encode_points_binary()`, rather than inventing a new limit — keeps results reproducible across repeated identical queries.
- **Time-collapsing convention:** both new functions reuse Day 23's existing `values[0]` simplification for time-varying flat-grid files, rather than introducing a second, different convention.
- **Frontend rendering:** scatter plots use Plotly's `scattergl` (WebGL) rather than `scatter` (SVG), matching the same WebGL-over-SVG reasoning already applied to the raster `ScatterplotLayer` on Day 23 — real-data point counts here reach into the tens of thousands, which would visibly lag under SVG rendering.
- **No time-dimension restriction:** unlike `TimeSeriesPanel`, the new `HistogramPanel`/`ScatterPanel` components have no swath-file restriction — both plot types work identically for swath and flat-grid files, since they depend only on `_get_subsetted_data()`, not on a time coordinate.

## 3. Backend Work Completed

**New Functions (`backend/processing/statistics.py`)**
- `compute_histogram()` — bins valid pixel values within a bounding box via `numpy.histogram`, reusing `_get_subsetted_data()` for subsetting/masking. Returns bin edges, counts, valid pixel count, mean, and std.
- `compute_scatter_correlation()` — independently subsets two variables over the same bbox/date/quality-flag parameters, intersects their validity masks, computes Pearson correlation (`numpy.corrcoef`), and applies the same stride-based subsampling cap as Day 23's point encoding above 500,000 pairs.

**New Endpoints (`backend/api/server.py`)**
- `/histogram` — same query parameters as `/stats` plus an optional `bins` (default 30).
- `/scatter` — same pattern, with `variable_x`/`variable_y` in place of a single `variable`.
- Both reuse the existing `_sanitize()` NumPy-scalar JSON safety net established since Day 5.

**Sidecar rebuild** — full clean rebuild (`rm -rf build dist *.spec` before `pyinstaller`), per this project's established "stale artifact" precaution, rather than an incremental build.

## 4. Backend Verification

**Source-level, real MODIS swath file, `chlor_a` / `Rrs_443`, bbox `[8,15,82,90]`:**
| Check | Result |
|---|---|
| Histogram valid pixel count | 67,299 |
| Scatter pair count | 67,299 of 67,299 (no subsampling triggered) |
| Correlation (chlor_a vs Rrs_443) | -0.1818 |

The histogram's 67,299 valid-pixel count was independently cross-checked against Day 23's already-verified `point_count` for the identical query (`encode_points_binary()` test) — an exact match, confirming `compute_histogram()`'s reuse of `_get_subsetted_data()` pulls the same subsetted pixel set as the already-proven raster path rather than diverging.

The correlation sign is physically sensible and worth noting rather than treating as a red flag: higher chlorophyll concentration increases blue-light absorption, which *lowers* reflectance at 443nm — a negative correlation is the expected real-world relationship, not an anomaly.

**Sidecar verification (curl, through the actual compiled binary):**
- Initial curl attempts returned `{"detail":"Not Found"}` — root-caused as the same stale-sidecar-process pattern first seen on Day 5: the binary file on disk had been replaced, but the already-running Tauri app was still serving the old in-memory process, unaware `/histogram`/`/scatter` existed. Resolved by fully restarting the app (`pkill` the stale process, relaunch `tauri dev`) rather than assuming a code defect.
- After restart: both endpoints returned results identical to the source-level test — same `valid_pixel_count: 67299`, same `correlation: -0.18175438809678626` to 15 decimal places. No drift between source and compiled artifact.

## 5. Frontend Work Completed

**New Components**
- `HistogramChart.tsx` / `HistogramPanel.tsx` — single-variable picker, bbox fields, Plotly bar chart from bin edges/counts (converted to center + width, since Plotly's bar type expects centers, not raw edges).
- `ScatterChart.tsx` / `ScatterPanel.tsx` — two-variable picker (X/Y), bbox fields, Plotly `scattergl` chart from paired x/y arrays, with a subsampling indicator shown in the caption when applicable.
- Both panels reuse `TimeSeriesPanel.css`'s existing class names (`timeseries-panel`, `field-group`, `bbox-fieldset`, `bbox-grid`, `validation-error`) rather than duplicating styles, since the layout is structurally identical minus the mode toggle/directory picker.

**`backendApi.ts`**
- `fetchHistogram()` / `fetchScatter()` added, following the same typed-wrapper and error-handling pattern as the existing `fetchRaster()`/`fetchTimeseriesWithinFile()`.

**`App.tsx` Integration**
- `HistogramPanel` and `ScatterPanel` wired in as siblings of `TimeSeriesPanel`/`ParameterSelector`, each given a distinctly namespaced remount key (`` `histogram-${ingestedFilePath}` ``, `` `scatter-${ingestedFilePath}` ``) from the start — directly applying Day 25's lesson (sibling key-collision bug) rather than risking a repeat.

## 6. Testing Summary

All testing performed live through the actual desktop app, per this project's established UI verification standard.

| Test | Result |
|---|---|
| Histogram, real MODIS swath file, `chlor_a`, bbox `[8,15,82,90]` | ✅ 67,299 valid pixels, mean 0.2804, std 1.0404 — exact match to curl-verified backend output |
| Scatter, same file, `chlor_a` vs `Rrs_443`, same bbox | ✅ 67,299 pixel pairs, correlation -0.1818 — exact match |
| Scatter, same variable selected for X and Y | ✅ Client-side guard ("Select two different variables to correlate") caught before any backend call |
| Histogram + scatter, flat-grid synthetic file (`sample_oceancolor.nc`), bbox `[33,36,-123,-120]` | ✅ Both work correctly on the non-swath path: 773 valid pixels/pairs, histogram mean 2.4278, scatter correlation 0.0333 |
| Repeated load of the same file 4× in one session (regression check for Day 25's Bug 1/3 pattern) | ✅ No duplicate panels, no stale state carried over — key namespacing held from the start |

No bugs were found or fixed during this block — a first for this project's Phase 3 work, and attributed directly to front-loading the design decisions (data shape, subsampling convention, key namespacing) before writing code, plus reusing already-proven backend logic (`_get_subsetted_data()`) rather than building new subsetting paths.

## 7. Outcome
- Histogram and scatter-plot parameter correlation are both fully implemented, verified at the source level, cross-validated against already-proven Day 23 raster values, confirmed through the actual compiled sidecar, and tested live in the UI against both real satellite data and the synthetic flat-grid fixture.
- The stale-sidecar-process pattern (Day 5's original discovery) recurred once this block but was correctly diagnosed and resolved without mistaking it for a code defect — reinforcing that a full app restart, not just a binary file replacement, is required after any backend rebuild.
- Day 25's key-namespacing lesson was applied proactively rather than reactively, and held up under the same repeated-load regression test that exposed the original bug.
- All Phase 3, Days 26-28 exit-criteria items met: auxiliary plots (histograms and scatter plots) built and verified for parameter correlation, across both file structures this project supports.

## 8. Next Steps (Week 5, Day 29 onward)
Begin Week 5: refine UI styling to mimic professional NASA Giovanni layouts (Day 29), then implement interactive tooltips on maps and charts for exact pixel value inspection (Day 30), followed by Days 31-35's integration and stress testing to close out Phase 3 ahead of the August 24 Week 5 checkpoint.