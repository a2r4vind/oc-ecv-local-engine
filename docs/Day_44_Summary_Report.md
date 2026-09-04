# Day 44 Summary Report — OC-ECV Local Engine

**Date:** September 4, 2026 (Phase 5, Day 44)
**Phase:** 5 — Comprehensive Testing, Packaging & Deployment
**Status:** Complete — two genuine, independently verified bugs found and fixed; one confirmed-but-unfixed issue carried forward with strong new evidence; one bug newly discovered and documented, not yet fixed

## 1. Objective
Begin Days 44-46's memory leak detection and UI glitch sweep per the milestone doc. Instrument the sidecar's exit handling, establish an RSS-monitoring baseline, run an extended real-usage stress session, and determine whether carried-forward issue #4 (DeckGLOverlay/useControl canvas cleanup) compounds under genuine repeated mounts rather than just React StrictMode's synthetic double-invoke.

## 2. Work Completed

**Sidecar Lifecycle Instrumentation (`frontend/src-tauri/src/lib.rs`)**
- Replaced the discarded `(mut _rx, _child)` spawn pattern with a managed `SidecarHandle` (`Mutex<Option<CommandChild>>`), giving the app an explicit, held reference to the sidecar process rather than dropping it at the end of `.setup()`.
- Added an async task piping the sidecar's stdout/stderr into the Tauri dev console (`[oc-ecv-backend stdout/stderr]` prefixed), directly addressing carried-forward issue #1's follow-up ("capture Tauri's piped stdout/stderr at failure moment") — this is now always-on rather than something to add reactively if the crash recurs.
- Added an explicit `RunEvent::ExitRequested | RunEvent::Exit` handler that terminates the sidecar on app close.

**RSS Monitoring Harness (`backend/day44_memory_leak_session.py`, new)**
- Two modes: `monitor` (passive RSS sampling alongside manual UI testing) and `backend-stress` (automated repeated ingest/stats/raster/histogram calls, no UI involved — isolates sidecar-side effects from webview-side effects).
- Sums RSS across each matched process **and all descendants recursively**, necessary because the PyInstaller `--onefile` bootloader double-forks into a separate worker process holding the real memory.
- Imports `REAL_BATCH_DATA` from `backend/config/paths.py` for test file resolution, consistent with the project's centralized path-resolution convention.

**Frontend Manual Checklist (`docs/Day_44_Frontend_Checklist.md`, new)**
- Core stress loop (load file → query all 4 analysis tabs → Change file, repeated 20-30×) designed specifically to exercise `MapView`'s real mount/unmount cycle, since `App.tsx`'s `{hasFile && (...)}` conditional means every "Change file" click is a genuine unmount, not a synthetic StrictMode double-invoke.
- Also covers bboxByMode isolation re-check, WebKitGTK layout workaround re-verification, and sidecar crash-watch procedure.

## 3. Bugs Found and Fixed

### Bug #1 — Sidecar worker process orphaned on app exit

**Found via:** Manual `ps aux` verification immediately after applying the `lib.rs` instrumentation, before trusting any RSS baseline.

**Root cause:** The PyInstaller `--onefile` bootloader double-forks into a separate worker process. `child.kill()` (called on the `CommandChild` handle) only terminates the bootloader PID; the forked worker (observed holding ~138MB RSS) survived the app's close button being clicked, confirmed directly via `ps aux` showing the worker PID still alive after the window closed.

**Fix:** Added `pkill -P <bootloader_pid>` (via `std::process::Command`) before calling `child.kill()` inside the `RunEvent::Exit` handler — kills the worker (the bootloader's child) first, then the bootloader itself.

**Verification:** Rebuilt, launched, confirmed both PIDs present via `ps aux`; closed the app window; confirmed via `ps aux` that both PIDs were gone. Repeated across two separate launch/close cycles with clean results both times.

### Bug #2 — Query cache silently non-persistent in the compiled sidecar (NEW finding, not previously documented)

**Found via:** Investigating why `backend/cache/query_cache.db` (checked via plain `ls`) showed a stale August 30 timestamp despite dozens of `/stats`/`/raster` calls made during today's session. Traced via `lsof -p <sidecar_pid>` (which showed no `.db` file open, ruling out a lingering-handle explanation) and then `find` against the sidecar's actual `_MEI` bootloader extraction directory (visible in `lsof`'s loaded-library paths), which located the real, actively-written `query_cache.db` at `/tmp/_MEI8jkVn6/cache/query_cache.db`.

**Root cause:** `backend/caching/query_cache.py`'s `DB_PATH = Path(__file__).resolve().parent.parent / "cache" / "query_cache.db"` resolves correctly when run as source, but inside a PyInstaller `--onefile` frozen binary, `__file__` resolves to a path inside the bootloader's temp extraction directory (`/tmp/_MEIxxxxxx/`) — a fresh, randomly-named directory created on every launch. This means:
- Every "verified through the compiled sidecar" caching claim since Day 18 was checking real, correct behavior, but only **within a single continuous session** — no prior test ever restarted the app and re-checked the cache, so this never surfaced.
- The project-relative `backend/cache/query_cache.db` file has likely never been written by the actual shipped/compiled app at all, only by source-run scripts.
- The cache was silently non-persistent across app restarts in the compiled build this entire time.

**Fix:** `DB_PATH` now branches on `sys.frozen`: when frozen, it anchors to `Path(sys.executable).resolve().parent / "cache" / "query_cache.db"` (a stable, on-disk location tied to the actual binary) instead of `__file__`.

**Verification:** Full source → compiled-artifact → restart-survival sequence:
1. Confirmed fresh rebuild via matching timestamps (`dist/oc-ecv-backend` and the copied `binaries/` file both matched `date` at build time).
2. Confirmed `sys.frozen` behaves as expected via a standalone throwaway PyInstaller build (`frozen: True`, `executable` pointing at the real binary path) — isolated the check from any project-specific complexity.
3. Discovered mid-verification that Tauri's `dev` workflow actually executes the sidecar from `frontend/src-tauri/target/debug/`, not `src-tauri/binaries/` — the fix's logic was correct throughout, but the "expected" stable location needed correcting to match Tauri's actual dev-mode behavior.
4. Ran one query, confirmed `query_cache.db` created at `target/debug/cache/`.
5. **Closed the app entirely, relaunched, ran zero new queries**, then queried `/history` directly — confirmed all 3 prior entries (across two separate sessions) were still present. This is the definitive pass: under the old bug this would have returned `{"total":0,"entries":[]}`.

**Flagged, not fixed:** `backend/config/paths.py`'s `BACKEND_ROOT` has the identical `Path(__file__).resolve()` construction. Currently low-risk since it's only used for `test_data/` resolution (not bundled/shipped in production, irrelevant inside the compiled app), but any future runtime-path use built on `BACKEND_ROOT` would inherit this same bug. Also flagged: this fix's "stable" verification path (`target/debug/`) is dev-mode-specific — Days 47-49's actual packaged installer will very likely place the sidecar binary somewhere else entirely (a bundle resources directory), so cache persistence needs one more explicit re-verification pass once packaging begins, rather than being assumed to carry over.

## 4. Confirmed But Not Yet Fixed: WebGL Context Leak (carried-forward issue #4, expanded scope)

**Evidence:** A 30-minute monitored stress session (`day44_memory_leak_session.py --mode monitor`, ~360 samples, 20+ manual load/query/switch/Change-file cycles per `Day_44_Frontend_Checklist.md`) produced:
- Webview RSS: 825 MB → peaked 5,830 MB → ended 4,606 MB (net growth 3,781 MB over the session; monotonically rising floor beneath a sawtooth surface, not simple noise).
- Repeated browser console errors: *"There are too many active WebGL contexts on this page, the oldest context will be lost."*

**Scope is broader than previously documented.** The console stack traces show **three distinct sources** creating WebGL contexts that are never disposed:
1. `_setupPainter` in `maplibre-gl.js` / `react-map-gl` — MapView's base map, recreated on every file load.
2. `_WebGLDevice` / `create` in a deck.gl chunk — `DeckGLOverlay`'s `MapboxOverlay`, exactly the component named in the original issue #4.
3. `wrapREGL` / `prepareRegl` in both `plotly.js-dist-min.js` and `react-plotly.js` — **a previously undocumented leak source.** `TimeSeriesChart`/`HistogramChart`/`ScatterChart` (Plotly-based) also create a WebGL context per mount/replot with no evidence of disposal.

**Isolating from sidecar effects:** A parallel `backend-stress` run (30 cycles, pure HTTP calls, zero UI interaction) showed webview RSS essentially flat (+22 MB) and sidecar RSS essentially flat (+7 MB) — confirming the large webview growth in the monitored session was driven specifically by real UI mount/unmount/replot activity, not by the app simply being open over time. This cleanly separates "webview canvas disposal" as the cause from any sidecar-side explanation.

**Not yet fixed.** Fixing this requires reviewing current source for `MapView.tsx`'s `DeckGLOverlay`, and `TimeSeriesChart.tsx`/`HistogramChart.tsx`/`ScatterChart.tsx`/`chartExport.ts`, to add explicit disposal (`overlay.finalize()`-equivalent for deck.gl; `Plotly.purge()` on unmount for the chart components) before writing any fix — deferred to Day 45 per the project's "never patch blind" convention.

## 5. Investigation Discipline Notes

Two separate false trails were run down and correctly resolved before reaching Bug #2's real root cause, consistent with this project's established "verify before trusting" pattern:
- Initially assumed a stale/not-yet-rebuilt binary when `binaries/cache/` came up empty post-fix — ruled out via explicit timestamp comparison (`ls -la` vs `date`) before considering the fix itself broken.
- Then isolated whether `sys.frozen` itself was unreliable in this specific PyInstaller build, via a fully standalone throwaway build — before finally identifying that Tauri's `dev` workflow runs the sidecar from `target/debug/`, not `binaries/`, which was the actual explanation.

Also worth noting for anyone reviewing this session cold: `lsof` returning empty for the cache `.db` file (Step 5, prior to locating `/tmp/_MEI8jkVn6/`) was correctly interpreted as expected behavior (SQLite connections are opened/closed per-call, not held open) rather than treated as evidence the cache wasn't working at all — avoided a wrong conclusion at that step.

## 6. Outcome

- Two real, independently verified bugs fixed: sidecar-exit orphaning (Bug #1) and cache non-persistence in the compiled binary (Bug #2, a genuinely new finding not previously suspected).
- Carried-forward issue #4 is now confirmed real under genuine repeated mounts (not just StrictMode) and its scope has expanded to include Plotly-based chart components, previously not implicated.
- Sidecar-side RSS growth during heavy real use is now understood to be at least partly attributable to genuine cache writes (each with a unique bbox-derived key) rather than assumed to be a leak — though this hasn't been fully separated from any residual growth; worth a closer look once the WebGL fix is in and a clean re-run is possible.
- All Day 44 exit-criteria items addressed: sidecar lifecycle hardened and verified, RSS monitoring infrastructure built and proven functional, a full 30-minute real-usage stress session executed and analyzed, and the specific priority question (does issue #4 compound under real usage) answered definitively — yes.

## 7. Next Steps (Day 45)

- Review current source for `MapView.tsx` (`DeckGLOverlay`), `TimeSeriesChart.tsx`, `HistogramChart.tsx`, `ScatterChart.tsx`, and `chartExport.ts`.
- Implement explicit WebGL context disposal on unmount/replot for all three identified sources (deck.gl overlay, MapLibre map instance, Plotly chart instances).
- Re-run the Day 44 monitoring harness (`day44_memory_leak_session.py --mode monitor`) after the fix, same stress-loop checklist, to confirm the webview RSS floor no longer climbs monotonically.
- Continue the remainder of the Days 44-46 UI glitch sweep (bboxByMode isolation re-check, WebKitGTK layout workaround re-verification at varying window sizes) not yet exercised this session.
- Carry forward: `paths.py`'s `BACKEND_ROOT` frozen-path fragility (low priority, documented); cache-persistence re-verification once Days 47-49 packaging produces a real installer (different binary location than dev-mode `target/debug/`).