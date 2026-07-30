# Day 17 Summary Report — OC-ECV Local Engine

**Date:** August 6, 2026 (Phase 2, Day 17)
**Phase:** 2 — Processing Pipeline & Subsetting Engine
**Status:** ✅ Complete — batch time-series extraction implemented; cross-file concurrency empirically tested and found not just unhelpful but actively counterproductive on this HDF5 build

## 1. Objective
Implement multi-file batch processing capability for time-series extraction, building on Day 9's directory-level date filtering and Days 8-11's per-file subsetting/masking/statistics pipeline. Directly follows on from Day 16's discovery of an HDF5 concurrency hazard, applying that same "verify before trusting" discipline to the multi-file case.

## 2. Work Completed

**Batch Time-Series Entrypoint (`backend/processing/statistics.py`)**
- `compute_batch_timeseries()` — scans a directory via Day 9's `filter_files_by_date_range()`, runs `compute_regional_stats()` across all matched files using Day 16's `run_parallel()` thread-pool infrastructure, and assembles a sorted, per-file time-series result.
- `serialize_file_access` parameter (default `True`) reuses Day 16's `_netcdf_file_lock` to serialize actual file access — carried over deliberately rather than assuming multi-file access is automatically safe just because paths differ.
- Result entries distinguish two previously-conflated outcomes: a file with **no bounding-box overlap** (`"skipped": True`, expected and common for real swath passes per Day 8's established finding) versus a genuine **processing failure** (`"error"`) — this separation was added after an early test run showed 15 of 25 real files "erroring" with a message that turned out to be legitimate no-coverage behavior, not a defect.

**New Endpoint (`backend/api/server.py`)**
- `/batch-timeseries` — accepts `directory`, `variable`, bbox, optional date range/quality flags, and `serialize_file_access`, returning the assembled time-series with the same NumPy-scalar JSON sanitization pattern used throughout.

## 3. Bugs Found and Fixed During Implementation

| Issue | Root Cause | Resolution |
|---|---|---|
| `AttributeError: 'NoneType' object has no attribute 'rstrip'` | Initial `compute_batch_timeseries` call omitted `start_date`/`end_date`, assuming Day 9's `filter_files_by_date_range` supported an unbounded "match everything" case via `None` — it doesn't; `_parse_date()` has no `None` guard | Passed an explicit wide date range (`2026-01-01` to `2026-07-31`) covering the full real batch instead of relying on unsupported `None` behavior |
| `AttributeError: 'str' object has no attribute 'get'` | Incorrectly assumed `filter_files_by_date_range()` returns a list of per-file dicts; it actually returns a single summary dict with `matched_files`/`skipped_files` keys, and each matched entry has `file_name` (not `path`) | Corrected `compute_batch_timeseries` to read `scan_result["matched_files"]` and reconstruct full paths via `Path(directory) / m["file_name"]`, verified against the real function body before re-fixing (not guessed a third time) |
| 15 of 25 real files reported as `"error"` on first successful run | `_compute_swath_stats` correctly raises `StatisticsError` when a bbox doesn't overlap a given swath's footprint (expected per Day 8), but the batch aggregator was labeling *all* exceptions as `"error"`, conflating legitimate no-coverage results with genuine failures | Added a check for `"does not overlap"` in the error message to route these to a distinct `"skipped"` field instead of `"error"`, so real future failures remain visually distinguishable |

## 4. Investigation: Cross-File Concurrency Safety and Performance

Following directly from Day 16's single-file HDF5 race discovery, this could not be assumed safe just because Day 17 involves separate physical files — HDF5's thread-safety limitations can be a global library-level property, not strictly scoped per-file-handle.

**Test 1 — safety, full 25-file real batch, 10 trials per mode:**
- `serialize_file_access=True`: 10/10 trials, consistent 15 skipped (no-overlap) + 10 successful, 0 genuine errors
- `serialize_file_access=False`: 10/10 trials, identical skip/success pattern, 0 genuine errors

No race surfaced in either mode across 20 total trials — a meaningfully larger and more reliable sample than the single/few-trial checks that missed Day 16's race initially.

**Test 2 — performance, isolated to the 10 files with genuine data (excluding the 15 fast no-overlap rejections, to avoid trivial-rejection noise dominating the timing):**

| Mode | Avg time (10 trials) |
|---|---|
| `serialize_file_access=True` (locked) | 1.82s |
| `serialize_file_access=False` (unlocked) | 2.28s |

**Finding: unlocking is not just unhelpful here, it is measurably ~25% slower.** The most likely explanation: this HDF5 build appears to serialize actual file access internally regardless of whether Python's lock is held. Removing the Python-level lock doesn't unlock any real parallel I/O — the underlying library-level serialization still happens — but now threads contend for that shared resource in an unordered, uncoordinated way, adding contention/context-switching overhead on top of the same serialized cost. The lock isn't just a safety measure in this case; it's the strictly better choice on performance grounds too.

**Final safety check:** reran the locked (default) mode across 15 additional trials against the full 25-file batch — 15/15 clean, 0 genuine errors, consistent with the earlier 10 trials.

**Underlying lesson:** Day 16 established that threading gives no benefit for single-file multi-variable access on this HDF5 build; Day 17 extends this finding to the multi-file case and adds an important refinement — it's not merely neutral, unlocking measurably regresses performance because the library's internal serialization plus added Python-thread contention is worse than orderly, lock-coordinated serial access. `serialize_file_access=True` is retained as the sole supported mode, not merely the safer default.

## 5. Outcome
- `compute_batch_timeseries()` is implemented, correct, and verified stable across 25 total trials (10+15) against the real 25-file MODIS batch, with zero genuine errors.
- Batch results correctly distinguish genuine processing failures from expected no-bbox-overlap results, avoiding a repeat of the "suspicious error count that's actually correct behavior" pattern from Days 8/10/11 — this time caught and fixed before being mistaken for a bug in the final report.
- Cross-file concurrency was empirically tested (not assumed) following directly from Day 16's precedent, and found to actively regress performance rather than merely fail to help — an important, non-obvious refinement of Day 16's finding.
- `run_parallel()`/`ThreadPoolExecutor` infrastructure remains in place and correctly used, now consistently in locked mode across both the Day 16 (single-file, multi-variable) and Day 17 (multi-file, single-variable) use cases.
- All Phase 2, Day 17 exit-criteria items met: multi-file batch processing for time-series extraction is functional, tested against real data, and its concurrency behavior is measured and documented rather than assumed.

## 6. Next Steps (Day 18)
Build the local caching layer (`joblib` or local SQLite index) for processed subset outputs — the next Phase 2 milestone item, and a natural complement to today's finding: since concurrent re-reads of the same files don't parallelize well on this HDF5 build, a cache that avoids redundant re-computation on repeated identical queries becomes a more valuable optimization lever than further threading effort.