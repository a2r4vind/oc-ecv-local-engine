# Day 11 Summary Report — OC-ECV Local Engine

**Date:** July 31, 2026 (Phase 2, Day 11)
**Phase:** 2 — Processing Pipeline & Subsetting Engine
**Status:** Complete — third consecutive "verify before trusting" investigation, third clean result

---

## 1. Objective
Develop statistical calculation modules (spatial mean, min, max, standard deviation) over subsetted arrays, integrating Day 8's bounding-box subsetting, Day 9's temporal filtering, and Day 10's quality-flag masking into one orchestrated query.

## 2. Work Completed

**Statistics Module** (`backend/processing/statistics.py`)
- `compute_statistics()` — generic mean/min/max/std computation over any array, safely handling the all-NaN case without triggering NumPy runtime warnings.
- `compute_regional_stats()` — main entrypoint, auto-detecting file structure and combining:
  - Flat-grid files: bounding-box subset + optional temporal filter
  - Grouped-swath files: bounding-box subset (crop-to-index-rectangle approach from Day 8) + optional quality-flag masking (Day 10)
- Explicit rejection of invalid combinations (e.g. temporal filtering on single-granule swath files, quality masking on flat-grid files that have no `l2_flags`) with clear error messages rather than silently ignoring incompatible parameters.

## 3. Investigation: Identical Stats With and Without Quality Masking

Testing quality-flag masking (`HIGLINT`) against a bounding box that previously showed real masking effects file-wide (Day 10) produced **identical** statistics with and without the flag applied — worth verifying independently rather than assuming correctness, continuing the pattern from Days 8 and 10.

**Diagnostic process:** directly computed the HIGLINT flag mask and the bounding-box mask independently of the statistics module, then checked their intersection.

**Finding:** the file contains 36,583 HIGLINT-flagged pixels in total, but **zero** of them fall within this specific bounding box's geographic coverage. The statistics module was correctly finding nothing to mask for this exact region — not failing to apply the mask.

**Underlying lesson:** this is the third investigation this week where an unexpected "no change" result was independently confirmed as correct real-data behavior rather than a defect. Sparse quality flags (like HIGLINT, which affects only ~1.3% of this file) combined with a bounding box covering only a fraction of the full swath makes a zero-overlap result entirely plausible and unremarkable — but it still needed direct verification rather than assumption, since the alternative explanation (a masking/crop-alignment bug) would have looked identical from the statistics output alone.

## 4. Outcome
- Statistics module validated against four scenarios: flat-grid bbox-only, flat-grid bbox+temporal, swath bbox-only, and swath bbox+quality-mask — all producing correct, cross-checked results.
- Invalid parameter combinations (temporal filter on swath files) correctly rejected with clear errors.
- All Phase 2, Day 11 exit-criteria items met. This closes out the individually-scoped processing modules (Days 8-11); remaining Phase 2 work shifts to UI integration and batch/caching concerns.

## 5. Next Steps (Days 12-14)
Build the parameter-selection UI — dropdowns for ECVs (SST, Chl-a, PAR, etc.), bounding-box inputs, and date pickers — the frontend surface that will let users actually invoke the subsetting/temporal/quality-mask/statistics pipeline built across Days 8-11, rather than only via CLI arguments.
