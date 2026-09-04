# Day 44 — Frontend Memory Leak & UI Glitch Checklist

Run `day44_memory_leak_session.py --mode monitor --duration-min 30` in a
terminal alongside this checklist. Note the elapsed-seconds shown in that
terminal's output next to each cycle below, so RSS samples can be correlated
back to specific actions afterward.

## Setup
- [ ] `pkill -f oc-ecv-backend` first (stale-process precaution, per standard
      rebuild routine)
- [ ] Confirm no other `oc-ecv-backend` or webview process already running
      (`ps aux | grep oc-ecv`) before starting — a leftover process from an
      earlier session would corrupt the baseline
- [ ] Launch `npm run tauri dev`, note startup webview + sidecar RSS from the
      monitor script's first sample as baseline
- [ ] Have both a real MODIS swath file and a flat-grid synthetic file
      (`test_data/synthetic/sample_oceancolor.nc`) ready to load

## Core stress loop — repeat 20–30×
This is the direct repro path for carried-forward issue #4
(DeckGLOverlay/useControl canvas cleanup) — `MapView` fully unmounts on
"Change file" per `{hasFile && (...)}` in App.tsx, so this loop is a real
mount/unmount cycle each time, not synthetic.

For each cycle:
- [ ] Load a file (alternate real swath / synthetic flat-grid across cycles)
- [ ] Query tab: set a bbox, Run Query (exercises raster fetch + BitmapLayer
      or ScatterplotLayer)
- [ ] Switch to Time Series tab, run a within-file or batch query
- [ ] Switch to Histogram tab, run a query
- [ ] Switch to Scatter tab, run a query
- [ ] Switch to History tab, confirm the just-run queries appear
- [ ] Click "Change file" (unmounts MapView/DeckGLOverlay)
- [ ] Note cycle number + elapsed time from the monitor script's console output

**Watch for (record if seen, don't just note pass/fail):**
- [ ] Any visible lag/stutter increasing as cycles progress (possible
      indirect leak symptom, not just a memory-graph number)
- [ ] Console errors on unmount/remount (check DevTools console specifically
      around each "Change file" click — issue #4's failure mode is a canvas
      cleanup gap, which may surface as a WebGL context warning before it
      shows up as RSS growth)
- [ ] Any WebGL context lost / "too many active WebGL contexts" browser
      warning — the single most direct symptom if issue #4 is real and
      compounding, since each leaked DeckGLOverlay instance holds its own
      GL context

## bboxByMode isolation re-check (Day 22-24 architecture, not re-verified since)
- [ ] Set different bboxes in Query, Time Series, Histogram, and Scatter tabs
      independently, without running a query in between
- [ ] Switch between all 5 tabs repeatedly — confirm each tab's bbox stays
      exactly as set (no cross-contamination)
- [ ] Confirm switching tabs does NOT reset colormap/opacity (Day 24: these
      are deliberately persistent, not query-specific — verify this hasn't
      regressed)

## WebKitGTK layout workaround re-verification
- [ ] Resize the app window to several sizes (very narrow, very wide, default)
      at each size, confirm `.main-area` does not collapse to ~2px on first
      paint after a fresh app launch (not just after interacting)
- [ ] Specifically test: resize window BEFORE loading any file (no Plotly
      chart injection yet to force the incidental reflow that's historically
      masked this bug) — this is the scenario most likely to still show the
      collapse if the `width:100em` workaround is ever accidentally removed
      or overridden by a later CSS change

## Sidecar crash watch (carried-forward issue #1)
- [ ] If `oc-ecv-backend` crashes or becomes unresponsive at any point during
      the loop, do NOT restart it immediately — first check the Tauri dev
      terminal for `[oc-ecv-backend stderr]` / `Terminated` lines (now
      captured per the lib.rs fix) and copy the exact output before
      restarting, since this is the first session with actual crash-moment
      stdout/stderr visibility

## End of session
- [ ] Stop the monitor script (Ctrl+C), confirm CSV written under
      `docs/memory_logs/`
- [ ] Note final cycle count reached and total elapsed time
- [ ] Cross-reference any console errors/warnings noted above against the
      specific elapsed-time timestamps in the CSV, to see if RSS jumps
      correlate with specific cycles/actions rather than climbing uniformly