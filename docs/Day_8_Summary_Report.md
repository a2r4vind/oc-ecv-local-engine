# Day 8 Summary Report — OC-ECV Local Engine

**Date:** July 27, 2026 (Phase 2, Day 8)
**Phase:** 2 — Processing Pipeline & Subsetting Engine
**Status:** Complete — validated against both synthetic and real data, including a resolved false-alarm investigation

---

## 1. Objective
Build bounding-box coordinate slicing functions using `xarray`, supporting both flat-grid (L3-style) and grouped-swath (real L2) file structures established during Phase 1.

## 2. Work Completed

**Subsetting Module** (`backend/processing/subsetting.py`)
- `subset_flat_grid()` — direct `xarray` `.sel()` slicing for 1D lat/lon coordinate files, correctly handling both ascending and descending coordinate ordering.
- `subset_swath()` — for 2D per-pixel lat/lon swath data: builds a boolean mask of in-bounds pixels, crops to the smallest bounding index-rectangle containing any matches (efficient — avoids operating on the full swath), then masks remaining out-of-bbox pixels within that rectangle as NaN.
- `subset_by_bbox()` — main entrypoint, auto-detecting file structure and dispatching accordingly; returns a JSON-serializable summary (shape, valid/total pixel counts, min/max/mean) rather than raw arrays.
- Input validation (`_validate_bbox`) and a dedicated `SubsettingError` for clean, specific error messages on bad boxes.

## 3. Investigation: Repeated Zero-Valid-Pixel Results on Real Data

Three consecutive test bounding boxes over the Arabian Sea (west coast of India) returned 0, 3, and 0 valid pixels respectively against the real MODIS granule — enough repetition to warrant a full diagnostic rather than assuming bad luck.

**Diagnostic process:**
1. Checked whole-file `chlor_a` validity — found only ~4.2% of the entire granule was valid (heavy cloud/land masking), establishing that sparse results were plausible in principle.
2. Directly extracted the lat/lon coordinates of pixels that *were* valid, independent of the subsetting code, to rule out a masking/alignment bug.

**Finding:** the granule's valid data was concentrated at lat 5.7–18.2°N, lon 79.4–93.9°E (Bay of Bengal / India's east coast) — while all three test boxes targeted the Arabian Sea (west coast, lon 68–80°E). The western portion of this particular swath pass was cloud-obscured; the eastern portion was clear. Confirmed shapes of `chlor_a`, `latitude`, and `longitude` all matched `(2030, 1354)` with no transpose/alignment issue.

**Resolution:** a fourth test box targeting the confirmed-valid region (lat 8-15, lon 82-90) returned a healthy 9.68% valid fraction with sensible min/max/mean values, closing out the investigation. No bug existed — three consecutive misses were a real consequence of a single swath pass having very unevenly distributed cloud cover across its full width.

**Underlying lesson:** for swath-geometry products, a bounding box's "coverage" and a granule's "valid data" are two independent things — a box can sit entirely within the swath's geographic footprint while still capturing near-zero valid pixels if that specific sub-region happened to be cloudy on that specific pass. Any future testing or UI messaging around real Ocean Color data should account for this rather than treating a low valid-pixel-fraction as automatically indicative of a bug.

## 4. Outcome
- Both subsetting code paths (flat-grid and grouped-swath) validated as functioning correctly against real satellite data, including edge cases of very sparse valid-data regions.
- Established a repeatable diagnostic pattern (check whole-file validity → check valid-pixel coordinates directly → compare to test box) for distinguishing genuine data sparsity from actual code bugs — useful for Days 9-11's continued subsetting/masking/stats work.
- All Phase 2, Day 8 exit-criteria items met.

## 5. Next Steps (Day 9)
Implement temporal filter logic (date-range extraction), building on the bounding-box subsetting foundation established today.
