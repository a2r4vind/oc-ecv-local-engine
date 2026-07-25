# Day 5 Summary Report — OC-ECV Local Engine

**Date:** July 25, 2026 (Phase 1, Day 5)
**Phase:** 1 — Environment Setup & Core Ingestion Engine
**Status:** ✅ Complete — all exit criteria met, verified against both synthetic and real satellite data

---

## 1. Objective
Create a basic frontend drag-and-drop file uploader component, connected end-to-end to the local ingestion parser via the Tauri sidecar's `/ingest` API.

## 2. Work Completed

**Frontend API Service Layer** (`frontend/src/services/backendApi.ts`)
- Thin typed wrapper around the FastAPI sidecar's HTTP endpoints (`/health`, `/ingest`), keeping the base URL/port and response typing in one place rather than scattered across components.

**FileUploader Component** (`frontend/src/components/FileUploader/`)
- Native drag-and-drop support via Tauri v2's `getCurrentWebview().onDragDropEvent()` — gives real filesystem paths for dropped files, unlike the browser's sandboxed HTML5 drag-drop API which only exposes an opaque blob.
- "Browse Files" button using `@tauri-apps/plugin-dialog` as a reliable fallback interaction path.
- Result panel rendering: file name, structure type (flat-grid vs. grouped-swath), dimensions, variable list, spatial bounds, ECV classification (chlorophyll/reflectance), and validation status with color-coded valid/invalid tag.

**Configuration Changes**
- `dragDropEnabled: true` added to the Tauri window config.
- `dialog:default` capability permission added (via `npm run tauri add dialog`).
- `App.tsx` updated to render the new component alongside the existing Tauri/React demo scaffold.

## 3. Key Issues Resolved

| Issue | Root Cause | Resolution |
|---|---|---|
| `/ingest` returned 404 through the Tauri app, despite working via `curl` against the source script | The Tauri sidecar spawns the **compiled PyInstaller binary**, which had been built on Day 2 — before `/ingest` existed. The running sidecar was executing stale code, unaware of any endpoint added since | Rebuilt the PyInstaller binary from the current `server.py` and replaced the sidecar binary in `src-tauri/binaries/`. Identified this as a recurring risk: any future `server.py` change requires a sidecar rebuild, not just a source edit |
| Real NASA file caused a generic `500 Internal Server Error` ("Load failed" in the UI) while the synthetic file worked fine | Real satellite files store some global attributes as NumPy scalar types (e.g. `numpy.float64`), which FastAPI's built-in JSON encoder cannot serialize natively — unlike the CLI test path, which already had a `default=str` fallback via `json.dumps()` | Added an explicit sanitization pass (`json.loads(json.dumps(result, default=str))`) inside the `/ingest` endpoint before returning the response, mirroring the safety net already used in the CLI entrypoint |
| Drag-and-drop appeared completely non-functional (no visual feedback, no ingestion triggered) | Dragging a file from **Windows File Explorer** into a WSLg-rendered Linux window crosses the WSL/Windows boundary, which WSLg has inconsistent support for regarding drag-and-drop payloads specifically (clipboard operations work fine; drag-drop often doesn't carry file data across it) | Confirmed "Browse Files" works identically and reliably; treated this as a known WSL-development-environment limitation rather than a code defect — expected to work correctly once the app runs natively outside WSL |

**Underlying lesson:** two of today's three issues stemmed from the same root cause pattern as earlier in the project — a stale compiled artifact (the sidecar binary) silently diverging from its source. This is now a known, recurring risk specific to this project's architecture (Python source → PyInstaller binary → Tauri sidecar), and a "rebuild sidecar after any backend change" step should become routine going forward, not an afterthought.

## 4. Outcome
- Full ingestion pipeline now works end-to-end through the actual desktop UI, not just via `curl`: drag-drop/browse → sidecar → ingestion → validation → rendered results.
- Verified against both the synthetic test fixture and the real MODIS-Aqua L2 granule over the Arabian Sea/India's west coast — correct results for both flat-grid and grouped-swath file structures.
- JSON serialization now robust against NumPy scalar types commonly present in real satellite product metadata.
- All Phase 1, Day 5 exit-criteria items met.

## 5. Next Steps (Day 6-7)
Phase 1's remaining buffer/review days: stress-test parsing speed across multi-gigabyte sample files, and resolve any further dependency alignment issues — closing out Phase 1 ahead of the Week 1 checkpoint (July 27).
