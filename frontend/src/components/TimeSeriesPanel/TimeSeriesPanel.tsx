import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import DatePickerField from "../DatePickerField/DatePickerField";
import TimeSeriesChart from "../TimeSeriesChart/TimeSeriesChart";
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

interface TimeSeriesPanelProps {
  filePath: string;
  availableVariables: string[];
  defaultBbox: {
    latMin: number;
    latMax: number;
    lonMin: number;
    lonMax: number;
  } | null;
  supportsWithinFile: boolean; // false for swath files (single time window)
}

export default function TimeSeriesPanel({
  filePath,
  availableVariables,
  defaultBbox,
  supportsWithinFile,
}: TimeSeriesPanelProps) {
  const [mode, setMode] = useState<Mode>(supportsWithinFile ? "within-file" : "batch");
  const [variable, setVariable] = useState(availableVariables[0] || "");

  const [latMin, setLatMin] = useState(defaultBbox ? String(defaultBbox.latMin) : "");
  const [latMax, setLatMax] = useState(defaultBbox ? String(defaultBbox.latMax) : "");
  const [lonMin, setLonMin] = useState(defaultBbox ? String(defaultBbox.lonMin) : "");
  const [lonMax, setLonMax] = useState(defaultBbox ? String(defaultBbox.lonMax) : "");

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [directory, setDirectory] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<NormalizedTimeSeries | null>(null);

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
    setChartData(null);

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
          setChartData(normalizeWithinFileResult(result));
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
          setChartData(normalizeBatchResult(result));
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
            <input type="number" step="any" value={latMin} onChange={(e) => setLatMin(e.target.value)} />
          </label>
          <label>
            Lat max
            <input type="number" step="any" value={latMax} onChange={(e) => setLatMax(e.target.value)} />
          </label>
          <label>
            Lon min
            <input type="number" step="any" value={lonMin} onChange={(e) => setLonMin(e.target.value)} />
          </label>
          <label>
            Lon max
            <input type="number" step="any" value={lonMax} onChange={(e) => setLonMax(e.target.value)} />
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
        <div className="date-grid">
          <DatePickerField label="Start date" value={startDate} onChange={setStartDate} />
          <DatePickerField label="End date" value={endDate} onChange={setEndDate} />
        </div>
      </fieldset>

      <button type="button" onClick={handlePlot} disabled={loading}>
        {loading ? "Loading…" : "Plot Time Series"}
      </button>

      {error && <div className="validation-error">⚠ {error}</div>}

      {chartData && (
        <TimeSeriesChart
          data={chartData}
          variable={variable}
          title={mode === "within-file" ? "Within-File Time Series" : "Batch Time Series"}
        />
      )}
    </div>
  );
}