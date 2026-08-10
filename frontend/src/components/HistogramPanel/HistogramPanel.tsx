import { useState } from "react";
import HistogramChart from "../HistogramChart/HistogramChart";
import { fetchHistogram, type HistogramResult } from "../../services/backendApi";
import "../TimeSeriesPanel/TimeSeriesPanel.css";

interface HistogramPanelProps {
  filePath: string;
  availableVariables: string[];
  defaultBbox: {
    latMin: number;
    latMax: number;
    lonMin: number;
    lonMax: number;
  } | null;
}

export default function HistogramPanel({
  filePath,
  availableVariables,
  defaultBbox,
}: HistogramPanelProps) {
  const [variable, setVariable] = useState(availableVariables[0] || "");

  const [latMin, setLatMin] = useState(defaultBbox ? String(defaultBbox.latMin) : "");
  const [latMax, setLatMax] = useState(defaultBbox ? String(defaultBbox.latMax) : "");
  const [lonMin, setLonMin] = useState(defaultBbox ? String(defaultBbox.lonMin) : "");
  const [lonMax, setLonMax] = useState(defaultBbox ? String(defaultBbox.lonMax) : "");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<HistogramResult | null>(null);

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
    setResult(null);

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
        setResult(res);
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

      <button type="button" onClick={handlePlot} disabled={loading}>
        {loading ? "Loading…" : "Plot Histogram"}
      </button>

      {error && <div className="validation-error">⚠ {error}</div>}

      {result && <HistogramChart data={result} variable={variable} />}
    </div>
  );
}