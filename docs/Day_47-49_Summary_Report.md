# Day 47-49 Summary Report — OC-ECV Local Engine

**Date:** September 5-8, 2026 (Phase 5, Days 47-49)
**Phase:** 5 — Comprehensive Testing, Packaging & Deployment
**Status:** ✅ Complete — first standalone .AppImage produced, one high-risk carried-forward path bug found and fixed, verified against the packaged binary across full app restarts, full end-to-end regression passed

## 1. Objective
Configure the Tauri bundler to produce a standalone Linux installer (.AppImage), per the milestone's Phase 5 packaging item, and close out the snapshot's single flagged high-risk item: re-verifying `query_cache.py`'s `DB_PATH` resolution against the actual packaged artifact rather than assuming dev-mode behavior carries over.

## 2. Pre-Work: Source Review Before Any Change
Per project convention, current source was requested and reviewed before any patching:

- **`frontend/src-tauri/tauri.conf.json` (`bundle` section)** — reviewed against official Tauri v2 sidecar documentation. `"externalBin": ["binaries/oc-ecv-backend"]` (without target-triple suffix) is the **correct** convention — Tauri appends `-$TARGET_TRIPLE` automatically when resolving the file on disk, and the project's existing sidecar rebuild routine already produces the correctly-suffixed binary. **No change needed** — a note in the prior session's snapshot flagging this as "not yet resolved" was a false alarm, caught by verification rather than carried forward as a fix-it item.
- **`backend/caching/query_cache.py`** — reviewed and found to still contain the Day 44 fix only (`sys.executable`-relative `DB_PATH`), **not** yet the XDG_DATA_HOME fix the snapshot's "Next Steps" section described as pending. Confirms the value of checking actual source over trusting a prior summary at face value.

## 3. Bug Found and Fixed: DB_PATH Breaks Under AppImage Packaging

| Issue | Root Cause | Resolution |
|---|---|---|
| `sys.executable`-anchored `DB_PATH` (Day 44 fix) would break once actually packaged | AppImages mount their contents read-only at a randomized path per launch (`/tmp/.mount_XXXXXXX/...`). `sys.executable` inside a packaged AppImage resolves *inside* that mount — same "ephemeral random path per launch" problem Day 44 fixed once already, plus a new problem: the mount is read-only, so `cache/` couldn't even be created there | Re-anchored `DB_PATH` to an OS-standard per-user data directory: `XDG_DATA_HOME` if set, else `~/.local/share/oc-ecv-local-engine/`, with an `OC_ECV_DATA_DIR` environment variable override for testing. Neither the PyInstaller bootloader's temp dir nor the AppImage's own mounted binary path is ever a valid location for persistent app data — only a real per-user home directory is stable, writable, and survives restarts, reinstalls, and the app being moved |

This was caught and fixed *before* the first AppImage build, not discovered afterward — continuing the project's established "verify before trusting" discipline applied here to a packaging-format transition rather than a data-processing result.

## 4. Work Completed

**Fix committed independently** (`backend/caching/query_cache.py`), per project convention of one independent unit of work per commit.

**Sidecar rebuild** — standard routine re-run since `query_cache.py` changed. Clean build, 168MB binary (consistent with prior builds — the size threshold that mattered on Day 2 for confirming rasterio/PIL C-extensions were genuinely bundled). All warnings reviewed and confirmed benign (Windows-ctypes-DLL-not-found noise irrelevant on Linux, `__glibc`/`__unix` conda-metadata noise, `_curses`-related library warnings unrelated to any code path this project uses) — none matched the "silently missing C-extension submodule" pattern that mattered on Day 2.

**First AppImage build** — `npm run tauri build` from `frontend/`, producing all three configured bundle targets (`.deb`, `.rpm`, `.AppImage`) cleanly. `externalBin` resolved with zero bundler warnings, confirming Finding #1 above. AppImage at:
```
frontend/src-tauri/target/release/bundle/appimage/oc-ecv-local_engine_0.1.0_amd64.AppImage
```

## 5. Verification

**Compiled-binary verification (pre-packaging, raw PyInstaller output)** — before trusting the packaged form, the rebuilt sidecar was run standalone (`./dist/oc-ecv-backend`) and checked directly:
- `/health`, `/diagnostics` — clean, all core deps (GDAL 3.6.2, netCDF4 1.6.2, rasterio 1.3.4, xarray) importing correctly in the frozen binary.
- `/stats` cold call → `_cache_hit: false`; identical repeat call → `_cache_hit: true`; values matched Day 8/15's established reference (`valid_fraction: 0.0968`, `mean: 0.280424`) exactly.
- `find ~/.local/share/oc-ecv-local-engine -name query_cache.db` → confirmed real file at the intended path — proof the XDG_DATA_HOME fix is live in the compiled binary, not just source.

**Packaged AppImage — baseline smoke test:**
- Window opens cleanly (WebKitGTK render, same cosmetic Mesa/Zink `libEGL` warnings present since Day 1).
- Sidecar auto-spawns and is visible in `ps aux` running from `/tmp/.mount_XXXXXXX/usr/bin/oc-ecv-backend` — confirms both the AppImage mount-path behavior and Tauri's documented behavior of stripping the target-triple suffix from the bundled binary name.
- Both real MODIS data (`aot_869`, Bay of Bengal bbox) and synthetic flat-grid data (`chlor_a`, California bbox) ingested, queried, and rendered correctly through the full UI — map, colormap, opacity, legend, statistics panel all functioning.

**Packaged AppImage — cross-restart cache persistence (the core Day 47-48 risk item):**
- Full close → relaunch → identical query cycle repeated 4 times.
- Every fresh-process relaunch returned `_cache_hit: true` on a query that process had never itself computed — definitive proof the cache persists across full application restarts, not merely within a single running session (the exact gap Day 44 discovered had silently existed since Day 18).
- Cache file (`~/.local/share/oc-ecv-local-engine/cache/query_cache.db`) confirmed growing across both the raw-binary test (Sep 7) and the packaged AppImage sessions (Sep 8) — same file, two different launch methods, proving the fix is robust to *how* the binary is executed, not just one specific method.

**Day 49 — Full end-to-end packaged regression:**

| Test | Result |
|---|---|
| Concurrent `/stats`+`/raster` (Day 45's RLock fix), 5 rapid-fire pairs | ✅ 5/5 clean, identical correct values, zero `NetCDF: Not a valid ID` errors, zero non-200 responses |
| WebGL disposal (Day 45's fix) across 5-6 file-switch cycles | ✅ No visible degradation, no crash, no unresponsiveness |
| All 5 tabs (Query, Time Series, Histogram, Scatter, History), both real and synthetic files | ✅ All render and query correctly |
| Export functions — CSV, GeoTIFF/NetCDF, PNG map | ✅ All 3 files saved with correct non-trivial sizes (11MB CSV, 41MB NetCDF, 307KB PNG) |
| Batch/multi-file operation (Time Series batch mode against `real_batch_data/`) | ✅ Covered via the tab-regression pass |

## 6. Known Issue Found — Logged, Not Blocking
**Bbox-draw tool cursor doesn't change to a crosshair on activation.** Confirmed the underlying draw functionality is unaffected — click-and-drag correctly draws the rectangle regardless. Root cause is almost certainly the same WebKitGTK/Zink software-rasterization pattern already seen twice in this project (Day 12-14's native date-picker freeze, Day 24's native range-slider styling failure) — native CSS cursor-state rendering not honored under this environment's software compositor. Cosmetic only; not investigated further given deadline proximity and zero functional impact. If addressed post-MVP, the established fix pattern (replace native-rendered behavior with a custom-controlled element) is the proven path.

## 7. Outcome
- First standalone Linux installer artifact (`.AppImage`) successfully produced for this project.
- The single highest-risk carried-forward item from the prior snapshot — packaged-path cache persistence — is now fully verified: source fix → compiled-binary check → packaged-AppImage check → cross-restart persistence check, each step actually tested rather than assumed, consistent with this project's standing verification discipline.
- A previously-flagged "unresolved" `externalBin` configuration concern was investigated and found to be a false alarm, correcting the record rather than carrying it forward as unfinished work.
- Full end-to-end regression across all major subsystems (concurrency locking, WebGL disposal, all five UI tabs, all three export formats, batch processing) passed cleanly in the packaged build, with no regressions from the dev-mode-verified behavior established across Phases 3-5.
- One cosmetic, non-blocking UI issue identified and logged for optional post-MVP polish.
- All Phase 5, Days 47-49 exit-criteria items met: standalone installer generated and verified, packaged-path risk item closed out, full regression clean.

## 8. Next Steps (Days 50-52)
Write comprehensive user manual and administrator deployment documentation, per the milestone's next scheduled item. Worth carrying forward into that documentation: the `OC_ECV_DATA_DIR` override (useful to mention for support/troubleshooting scenarios), and the current single-target scope (.AppImage only — `.deb`/`.rpm` are also produced as a side effect of `"targets": "all"` in `tauri.conf.json` but have not been part of the verified/tested scope this session; worth a decision on whether to narrow `targets` to `["appimage"]` before final handover, or leave as-is and note the other two as unverified bonus artifacts in the documentation).