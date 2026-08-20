import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import DatePickerField from "../DatePickerField/DatePickerField";
import {
  fetchTimeseriesWithinFile,
  fetchBatchTimeseries,
} from "../../services/backendApi";
import {
  normalizeWithinFileResult,
  normalizeBatchResult,
  type NormalizedTimeSeries,
} from "../../utils/timeseries";
import "./TimeSeriesPanel.css";

type Mode = "within-file" | "batch";
type ParsedBbox = { latMin: number; latMax: number; lonMin: number; lonMax: number };

function bboxRoughlyEqual(a: ParsedBbox | null, b: ParsedBbox | null): boolean {
  if (a === null || b === null) return a === b;
  const EPS = 1e-6;
  return (
    Math.abs(a.latMin - b.latMin) < EPS &&
    Math.abs(a.latMax - b.latMax) < EPS &&
    Math.abs(a.lonMin - b.lonMin) < EPS &&
    Math.abs(a.lonMax - b.lonMax) < EPS
  );
}

interface TimeSeriesPanelProps {
  filePath: string;
  availableVariables: string[];
  supportsWithinFile: boolean; // false for swath files (single time window)
  // Reports the plotted result upward instead of rendering it inline —
  // AppShell displays it in the persistent right-side results area.
  onResult: (
    result: { data: NormalizedTimeSeries; variable: string; title: string } | null
  ) => void;
  // Option A (isolated per-panel bbox): reports this panel's own bbox
  // upward so the map's overlay rectangle can reflect it while this
  // panel/mode is active — independent of every other panel's bbox.
  onBboxChange?: (bbox: ParsedBbox | null) => void;
  // Phase C: this panel's bbox as owned by App.tsx's bboxByMode(.timeseries)
  // — synced into local field state when it changes for a reason other
  // than this panel's own last edit (i.e. a map-drag while this tab is
  // active). See ParameterSelector.tsx for the identical pattern.
  bbox?: ParsedBbox | null;
  // Phase B: this file's own valid date coverage — only meaningful for
  // "within this file" mode, since batch mode's range spans whatever
  // files exist in a chosen directory, not this one file's own steps.
  validDateRange?: { min: string; max: string } | null;
}

export default function TimeSeriesPanel({
  filePath,
  availableVariables,
  supportsWithinFile,
  onResult,
  onBboxChange,
  bbox,
  validDateRange,
}: TimeSeriesPanelProps) {

  const [mode, setMode] = useState<Mode>(supportsWithinFile ? "within-file" : "batch");
  const [variable, setVariable] = useState(availableVariables[0] || "");
  
  const [latMin, setLatMin] = useState("");
  const [latMax, setLatMax] = useState("");
  const [lonMin, setLonMin] = useState("");
  const [lonMax, setLonMax] = useState("");

  const lastEmittedRef = useRef<ParsedBbox | null>(null);

  function emitBboxChange(next: {
    latMin?: string;
    latMax?: string;
    lonMin?: string;
    lonMax?: string;
  }) {
    if (!onBboxChange) return;
    const values = {
      latMin: next.latMin ?? latMin,
      latMax: next.latMax ?? latMax,
      lonMin: next.lonMin ?? lonMin,
      lonMax: next.lonMax ?? lonMax,
    };
    const parsed = {
      latMin: parseFloat(values.latMin),
      latMax: parseFloat(values.latMax),
      lonMin: parseFloat(values.lonMin),
      lonMax: parseFloat(values.lonMax),
    };
    const allValid = Object.values(parsed).every((v) => !Number.isNaN(v));
    const result = allValid ? parsed : null;
    lastEmittedRef.current = result;
    onBboxChange(result);
  }

  // Phase C: sync fields from an externally-changed bbox (map drag).
  useEffect(() => {
    const incoming = bbox ?? null;
    if (bboxRoughlyEqual(incoming, lastEmittedRef.current)) return;

    if (incoming === null) {
      setLatMin("");
      setLatMax("");
      setLonMin("");
      setLonMax("");
    } else {
      setLatMin(String(incoming.latMin));
      setLatMax(String(incoming.latMax));
      setLonMin(String(incoming.lonMin));
      setLonMax(String(incoming.lonMax));
    }
    lastEmittedRef.current = incoming;
  }, [bbox]);
  
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [directory, setDirectory] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pickDirectory() {
    try {
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string") {
        setDirectory(selected);
      }
    } catch (err) {
      setError(
        err instanceof Error ? `Could not open folder picker: ${err.message}` : "Unknown error"
      );
    }
  }

  function parseBboxOrError() {
    const lm = parseFloat(latMin);
    const lx = parseFloat(latMax);
    const om = parseFloat(lonMin);
    const ox = parseFloat(lonMax);
    if ([lm, lx, om, ox].some((v) => Number.isNaN(v))) {
      setError("All four bounding-box fields are required.");
      return null;
    }
    if (lm >= lx || om >= ox) {
      setError("lat_min must be < lat_max, and lon_min must be < lon_max.");
      return null;
    }
    return { latMin: lm, latMax: lx, lonMin: om, lonMax: ox };
  }
  
  async function handlePlot() {
    setError(null);
    onResult(null);

    if (!variable) {
      setError("Select a variable.");
      return;
    }
    const bbox = parseBboxOrError();
    if (!bbox) return;

    setLoading(true);
    try {
      if (mode === "within-file") {
        const result = await fetchTimeseriesWithinFile({
          filePath,
          variable,
          latMin: bbox.latMin,
          latMax: bbox.latMax,
          lonMin: bbox.lonMin,
          lonMax: bbox.lonMax,
          startDate: startDate || undefined,
          endDate: endDate || undefined,
        });
        if (result.error) {
          setError(result.error);
        } else {
          onResult({
            data: normalizeWithinFileResult(result),
            variable,
            title: "Within-File Time Series",
          });
        }
      } else {
        if (!directory) {
          setError("Pick a directory for the batch time-series.");
          setLoading(false);
          return;
        }
        if (!startDate || !endDate) {
          setError("Start and end dates are required for batch time-series.");
          setLoading(false);
          return;
        }
        const result = await fetchBatchTimeseries({
          directory,
          variable,
          latMin: bbox.latMin,
          latMax: bbox.latMax,
          lonMin: bbox.lonMin,
          lonMax: bbox.lonMax,
          startDate,
          endDate,
        });
        if (result.error) {
          setError(result.error);
        } else {
          onResult({
            data: normalizeBatchResult(result),
            variable,
            title: "Batch Time Series",
          });
        }
      }
    } catch (err) {
      setError(err instanceof Error ? `Could not reach backend: ${err.message}` : "Unknown error");
    } finally {
      setLoading(false);
    }
  }
  


  return (
    <div className="timeseries-panel">
      <h2>Time Series</h2>

      <div className="timeseries-mode-toggle">
        <label>
          <input
            type="radio"
            name="ts-mode"
            checked={mode === "within-file"}
            disabled={!supportsWithinFile}
            onChange={() => setMode("within-file")}
          />
          Within this file
        </label>
        <label>
          <input
            type="radio"
            name="ts-mode"
            checked={mode === "batch"}
            onChange={() => setMode("batch")}
          />
          Batch across a directory
        </label>
      </div>
      {!supportsWithinFile && (
        <p className="timeseries-note">
          "Within this file" isn't available — this file represents a single
          satellite pass with no time dimension. Use "Batch across a
          directory" instead.
        </p>
      )}

      <div className="field-group">
        <label htmlFor="ts-variable-select">Variable (ECV)</label>
        <select
          id="ts-variable-select"
          value={variable}
          onChange={(e) => setVariable(e.target.value)}
        >
          {availableVariables.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="bbox-fieldset">
        <legend>Bounding Box</legend>
        <div className="bbox-grid">
           <label>
            Lat min
            <input
              type="number"
              step="any"
              value={latMin}
              onChange={(e) => {
                setLatMin(e.target.value);
                emitBboxChange({ latMin: e.target.value });
              }}
            />
          </label>
          <label>
            Lat max
            <input
              type="number"
              step="any"
              value={latMax}
              onChange={(e) => {
                setLatMax(e.target.value);
                emitBboxChange({ latMax: e.target.value });
              }}
            />
          </label>
          <label>
            Lon min
            <input
              type="number"
              step="any"
              value={lonMin}
              onChange={(e) => {
                setLonMin(e.target.value);
                emitBboxChange({ lonMin: e.target.value });
              }}
            />
          </label>
          <label>
            Lon max
            <input
              type="number"
              step="any"
              value={lonMax}
              onChange={(e) => {
                setLonMax(e.target.value);
                emitBboxChange({ lonMax: e.target.value });
              }}
            />
          </label>
        </div>
      </fieldset>

      {mode === "batch" && (
        <div className="field-group">
          <label>Directory</label>
          <div className="directory-picker">
            <input type="text" value={directory} readOnly placeholder="No directory selected" />
            <button type="button" onClick={pickDirectory}>
              Browse…
            </button>
          </div>
        </div>
      )}

      <fieldset className="date-fieldset">
        <legend>Date Range {mode === "batch" ? "(required)" : "(optional)"}</legend>
        {mode === "within-file" && validDateRange && (
          <p className="valid-range-note">
            Valid range: {validDateRange.min} to {validDateRange.max}
          </p>
        )}
        <div className="date-grid">
          <DatePickerField label="Start date" value={startDate} onChange={setStartDate} />
          <DatePickerField label="End date" value={endDate} onChange={setEndDate} />
        </div>
      </fieldset>

      <button type="button" onClick={handlePlot} disabled={loading}>
        {loading ? "Loading…" : "Plot Time Series"}
      </button>

      {error && <div className="validation-error">⚠ {error}</div>}
    </div>
  );
}