# Day 18 Summary Report — OC-ECV Local Engine

**Date:** August 7, 2026 (Phase 2, Day 18)
**Phase:** 2 — Processing Pipeline & Subsetting Engine
**Status:** Complete — SQLite caching layer implemented, verified for correctness, invalidation, and cache-key discrimination, confirmed live through the actual sidecar

## 1. Objective
Build a local caching layer for processed subset outputs, preventing redundant re-computation on repeated identical queries — directly motivated by Day 16-17's finding that this project's real bottleneck is disk I/O, not CPU-bound compute, making a cache a far more effective optimization lever than further threading effort.

## 2. Design Decision: SQLite over joblib
Both options were considered per the milestone doc's suggestion ("joblib or local SQLite index"). SQLite was chosen because:
- The cached outputs (`compute_regional_stats()` results) are already small JSON-serializable stats dicts, not raw pixel arrays — so joblib's main advantage (efficient large-object pickling) doesn't apply much here.
- A SQL table of past queries is naturally browsable, which directly sets up Day 39's milestone item ("processing history panel tracking previous user queries and parameters") — the same underlying table can be reused with a read-only browsing endpoint added later, rather than building two separate mechanisms.

## 3. Work Completed

**Cache Module (`backend/caching/query_cache.py`)**
- `_ensure_db()` — creates a `query_cache` SQLite table (path: `backend/cache/query_cache.db`, gitignored as local/regeneratable state) if it doesn't exist.
- `_compute_cache_key()` — hashes all query parameters (file path, variable, bbox, date range, quality flags) **plus the file's current modification time (`mtime`)** into a single cache key. Including `mtime` means the cache automatically invalidates if the underlying `.nc` file is ever edited/replaced, rather than requiring manual cache-clearing or risking silently stale results.
- `get_cached_result()` / `store_result()` — lookup and insert/update against the cache table, tracking `hit_count` per entry (useful groundwork for Day 39's history panel, showing which queries get repeated).

**Cached Wrapper (`backend/processing/statistics.py`)**
- `compute_regional_stats_cached()` — a thin wrapper around the existing `compute_regional_stats()`, checking the cache first and only computing (then storing) on a miss. Kept as a separate function rather than modifying `compute_regional_stats()` directly, so the original stays a pure, cache-free function usable by the CLI and any future non-cached call path.
- Adds a `_cache_hit: true/false` field to every response — deliberate, so cache behavior is directly observable in the output rather than inferred only from timing, making it possible to verify correctness rather than assume it.

**Endpoint Wiring (`backend/api/server.py`)**
- `/stats` now calls `compute_regional_stats_cached()` instead of `compute_regional_stats()` directly.
- `/stats-multi` and `/batch-timeseries` were deliberately left uncached for now — Days 16-17 already established specific, verified concurrency/locking behavior for those endpoints, and layering caching in immediately would introduce an untested interaction between the cache and the lock. Caching can be extended to those endpoints in a follow-up once `/stats` is proven stable.

## 4. Verification

**Correctness and speedup (first implementation test):**
| Call | Time | Cache hit |
|---|---|---|
| 1st (cold) | 0.442s | False |
| 2nd (same params) | 0.008s | True |

Results matched exactly (after excluding the `_cache_hit` field itself, which legitimately differs) — **~55x speedup** on a repeated identical query, substantially larger than any speedup achieved via threading on Days 16-17, confirming the I/O-avoidance hypothesis directly.

**Invalidation test:** queried once (hit expected on repeat), then called `os.utime()` to bump the file's mtime without changing its content (simulating a file edit), then queried again with identical parameters.
- Result: correctly forced a cache miss and recomputation (`_cache_hit: False`) after the touch — confirms the cache does not serve stale results when the underlying file changes.

**Cache-key discrimination test:** confirmed that (a) identical query parameters against the same file produce a cache hit, and (b) a different bounding box against the same file produces a cache miss — cache keys correctly discriminate on query parameters, not just file identity.

**Sidecar verification:** rebuilt the PyInstaller binary (server.py changed) and issued the same `/stats` query twice through the actual running Tauri sidecar (not just the source script):
- 1st call: `_cache_hit: false`, full computed stats returned.
- 2nd call: `_cache_hit: true`, identical stats returned.
Confirms the caching layer works correctly in the compiled production artifact, not only in source — consistent with the verification standard established after Day 16's race condition, where source-only testing had initially missed a real bug.

## 5. Outcome
- Local SQLite caching layer is implemented, correctness-verified (matching results, mtime-based invalidation, correct key discrimination), and confirmed working through the actual sidecar binary.
- Cache produces a substantially larger real-world speedup (~55x on a repeat query) than anything achieved via threading in Days 16-17, directly validating the project's shift in optimization strategy from "parallelize the I/O" to "avoid repeating the I/O."
- `backend/cache/query_cache.db` correctly excluded from version control via `.gitignore`, consistent with treating it as regeneratable local state rather than something to track.
- The underlying `query_cache` table's structure (per-query record with file/variable/bbox/date/flags and a hit counter) is directly reusable for Day 39's processing-history panel, avoiding duplicate work later.
- All Phase 2, Day 18 exit-criteria items met: local caching layer built, and demonstrated (not assumed) to prevent redundant computation on repeated identical queries.

## 6. Next Steps (Day 19-21, Buffer & Review)
Phase 2's remaining buffer/review days: end-to-end testing of the full processing pipeline across all 13 listed ECVs, closing out Phase 2 ahead of the August 10 Week 3 checkpoint. Worth considering as part of this buffer window: extending the cache wrapper to `/stats-multi` and `/batch-timeseries` now that `/stats` has proven the pattern stable, and deciding whether cache entries should have any eviction/expiry policy before the cache table grows unbounded over normal usage.