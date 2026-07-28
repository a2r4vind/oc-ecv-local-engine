# Days 12-14 Summary Report — OC-ECV Local Engine

**Date:** August 1-3, 2026 (Phase 2, Days 12-14)
**Phase:** 2 — Processing Pipeline & Subsetting Engine
**Status:** Complete — three real bugs found and fixed, all verified

---

## 1. Objective
Build the parameter-selection UI — dropdowns for ECVs, bounding-box inputs, and date pickers — giving the frontend the surface to assemble queries for the subsetting/temporal/quality-mask/statistics pipeline built across Days 8-11.

## 2. Work Completed

**ParameterSelector Component** (`frontend/src/components/ParameterSelector/`)
- Variable dropdown populated **dynamically from the currently ingested file's actual variable list** (excluding `l2_flags`), rather than a static hardcoded ECV list — guarantees the dropdown only ever shows genuinely queryable options for whatever file is loaded.
- Four bounding-box number inputs with client-side validation: range checks (-90/90 lat, -180/180 lon) and order checks (min < max).
- Date-range picker that only appears for flat-grid files, correctly hidden (replaced by an explanatory note) for single-granule swath files, matching the temporal-filtering rule established on Days 9 and 11.
- "Run Query" button assembling a structured `QueryParams` object, currently displayed as JSON pending Day 15's backend wiring.

**FileUploader Integration**
- Added an `onIngested` callback prop so `App.tsx` can receive the ingested file's path and metadata, lifting state up to feed `ParameterSelector`.

**Custom Calendar Component** (`frontend/src/components/DatePickerField/`)
- Built a fully custom, pure-React/CSS calendar picker (month navigation, click-to-select day grid) as an alternative to the native OS date-picker widget.

## 3. Bugs Found and Fixed

| Issue | Root Cause | Resolution |
|---|---|---|
| Native `<input type="date">` calendar popup froze the UI after selecting a start date — required minimizing/maximizing the window to interact with the end date | The native calendar overlay is rendered by WebKitGTK (Tauri's Linux webview engine) as an OS-level popup surface; under WSLg's software-rendering fallback (same class of issue as earlier `libEGL`/`MESA: ZINK` warnings seen since Day 1), this popup compositing appears to stall until a forced repaint | Replaced the native date input with a fully custom calendar component built from plain React elements — no OS-level popup surface involved, so it renders like any other part of the page |
| Loading a new file left the previous file's bounding-box/variable values in the form instead of resetting | React doesn't reset a component's internal state just because its props changed — `ParameterSelector`'s `useState` values persisted across file switches since it remained the same component instance | Added `key={ingestedFilePath}` to the `<ParameterSelector>` element in `App.tsx`, forcing React to fully remount (and reset) the component whenever the loaded file changes |
| Calendar day cells showed inconsistent box/highlight artifacts on seemingly random cells across two separate screenshots | Initially suspected native button chrome (fixed via `appearance: none`) but the real cause was column misalignment: the weekday header row (`S M T W T F S`) and the day-number grid below it used different CSS Grid `gap` values, causing their columns to drift out of alignment with each other row by row | Unified `gap: 2px` and `box-sizing: border-box` across both grids, confirmed correct by independently verifying the weekday math (Python's `datetime.date(2026,7,1).weekday()` confirmed July 1, 2026 is genuinely a Wednesday — the date logic was already correct; only the visual alignment needed fixing |

**Underlying lesson:** the date-picker freeze is the fourth WSLg-specific rendering quirk encountered in this project (after the AppImage `xdg-open` issue, the drag-and-drop cross-boundary limitation, and the EGL/software-rendering warnings) — a recurring pattern worth remembering: native OS-level popup/overlay widgets are the most likely thing to misbehave under WSLg's compositor, while custom-rendered in-page UI (plain divs/buttons) reliably avoids the issue entirely.

## 4. Outcome
- Parameter-selection UI fully functional and tested against both file structures: variable dropdown, bbox inputs, and conditional date-range picker all verified correct via screenshots at each step.
- Custom calendar picker resolves the WSLg freeze issue while additionally avoiding future dependency on native widget rendering behavior across platforms.
- Form correctly resets per loaded file, preventing stale query parameters from carrying over between files.
- All Phase 2, Days 12-14 exit-criteria items met.

## 5. Next Steps (Day 15)
Connect the UI's assembled query parameters to backend processing APIs — replacing the current JSON preview with an actual FastAPI endpoint call that invokes Day 11's `compute_regional_stats()` and renders real statistical results in the UI.
