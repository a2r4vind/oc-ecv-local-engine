import { useState } from "react";
import { fetchHistogram, type HistogramResult } from "../../services/backendApi";
import "../TimeSeriesPanel/TimeSeriesPanel.css";

interface HistogramPanelProps {
  filePath: string;
  availableVariables: string[];
  onResult: (result: (HistogramResult & { variable: string }) | null) => void;
  onBboxChange?: (
    bbox: { latMin: number; latMax: number; lonMin: number; lonMax: number } | null
  ) => void;
}

export default function HistogramPanel({
  filePath,
  availableVariables,
  onResult,
  onBboxChange,
}: HistogramPanelProps) {
  const [variable, setVariable] = useState(availableVariables[0] || "");
  const [latMin, setLatMin] = useState("");
  const [latMax, setLatMax] = useState("");
  const [lonMin, setLonMin] = useState("");
  const [lonMax, setLonMax] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    onBboxChange(allValid ? parsed : null);
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
      const res = await fetchHistogram({
        filePath,
        variable,
        latMin: bbox.latMin,
        latMax: bbox.latMax,
        lonMin: bbox.lonMin,
        lonMax: bbox.lonMax,
      });
      if (res.error) {
        setError(res.error);
      } else {
        onResult({ ...res, variable });
      }
    } catch (err) {
      setError(
        err instanceof Error ? `Could not reach backend: ${err.message}` : "Unknown error"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="timeseries-panel">
      <h2>Histogram</h2>
      <div className="field-group">
        <label htmlFor="hist-variable-select">Variable (ECV)</label>
        <select
          id="hist-variable-select"
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
      <button type="button" onClick={handlePlot} disabled={loading}>
        {loading ? "Loading…" : "Plot Histogram"}
      </button>
      {error && <div className="validation-error">⚠ {error}</div>}
    </div>
  );
}