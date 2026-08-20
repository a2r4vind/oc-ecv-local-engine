import { useState, useMemo } from "react";
import FileUploader from "./components/FileUploader/FileUploader";
import ParameterSelector, {
  type QueryParams,
} from "./components/ParameterSelector/ParameterSelector";
import MapView, {
  type MapBbox,
  type SpatialBounds,
} from "./components/MapView/MapView";
import {
  computeStats,
  fetchRaster,
  type IngestionResult,
  type StatsResult,
  type RasterResult,
  type HistogramResult,
  type ScatterResult,
} from "./services/backendApi";
import { COLORMAP_NAMES, type ColormapName } from "./utils/colormaps";
import ColorLegend from "./components/ColorLegend/ColorLegend";
import OpacitySlider from "./components/OpacitySlider/OpacitySlider";
import TimeSeriesPanel from "./components/TimeSeriesPanel/TimeSeriesPanel";
import HistogramPanel from "./components/HistogramPanel/HistogramPanel";
import ScatterPanel from "./components/ScatterPanel/ScatterPanel";
import TimeSeriesChart from "./components/TimeSeriesChart/TimeSeriesChart";
import HistogramChart from "./components/HistogramChart/HistogramChart";
import ScatterChart from "./components/ScatterChart/ScatterChart";
import type { NormalizedTimeSeries } from "./utils/timeseries";
import "./App.css";

type Mode = "stats" | "timeseries" | "histogram" | "scatter";

function App() {
  const [ingestedFilePath, setIngestedFilePath] = useState<string | null>(null);
  const [ingestedResult, setIngestedResult] = useState<IngestionResult | null>(null);

  // Option A: each panel/mode owns its own independent bbox. The map's
  // overlay rectangle shows whichever mode is currently active — it does
  // NOT sync across modes. Keyed by mode rather than one shared value.
  const [bboxByMode, setBboxByMode] = useState<Record<Mode, MapBbox | null>>({
    stats: null,
    timeseries: null,
    histogram: null,
    scatter: null,
  });

  const [activeMode, setActiveMode] = useState<Mode>("stats");

  const [statsLoading, setStatsLoading] = useState(false);
  const [statsResult, setStatsResult] = useState<StatsResult | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [rasterLoading, setRasterLoading] = useState(false);
  const [rasterResult, setRasterResult] = useState<RasterResult | null>(null);
  const [rasterError, setRasterError] = useState<string | null>(null);
  const [colormap, setColormap] = useState<ColormapName>("viridis");
  const [opacity, setOpacity] = useState(1);
  const [queriedVariable, setQueriedVariable] = useState<string | null>(null);

  const [tsResult, setTsResult] = useState<{ data: NormalizedTimeSeries; variable: string; title: string } | null
  >(null);
  const [histResult, setHistResult] = useState<(HistogramResult & { variable: string }) | null>(
    null
  );
  const [scatterResult, setScatterResult] = useState<ScatterResult | null>(null);

  function handleIngested(filePath: string, result: IngestionResult) {
    setIngestedFilePath(filePath);
    setIngestedResult(result);
    setStatsResult(null);
    setStatsError(null);
    setBboxByMode({ stats: null, timeseries: null, histogram: null, scatter: null });
    setRasterResult(null);
    setRasterError(null);
    setTsResult(null);
    setHistResult(null);
    setScatterResult(null);
    setActiveMode("stats");
  }

  // Properly resets back to the pre-upload state so the full FileUploader
  // reappears — replaces the earlier fake-ingest placeholder.
  function handleChangeFile() {
    setIngestedFilePath(null);
    setIngestedResult(null);
    setStatsResult(null);
    setStatsError(null);
    setBboxByMode({ stats: null, timeseries: null, histogram: null, scatter: null });
    setRasterResult(null);
    setRasterError(null);
    setTsResult(null);
    setHistResult(null);
    setScatterResult(null);
    setActiveMode("stats");
  }

  function setBboxForMode(mode: Mode) {
    return (bbox: MapBbox | null) => {
      setBboxByMode((prev) => ({ ...prev, [mode]: bbox }));
    };
  }

  async function handleQuerySubmit(params: QueryParams) {
    setStatsLoading(true);
    setStatsResult(null);
    setStatsError(null);
    setRasterLoading(true);
    setRasterResult(null);
    setRasterError(null);
    setQueriedVariable(params.variable);

    const query = {
      filePath: params.filePath,
      variable: params.variable,
      latMin: params.latMin,
      latMax: params.latMax,
      lonMin: params.lonMin,
      lonMax: params.lonMax,
      startDate: params.startDate,
      endDate: params.endDate,
    };

    const statsTask = (async () => {
      try {
        const result = await computeStats(query);
        if (result.error) setStatsError(result.error);
        else setStatsResult(result);
      } catch (err) {
        setStatsError(
          err instanceof Error ? `Could not reach backend: ${err.message}` : "Unknown error"
        );
      } finally {
        setStatsLoading(false);
      }
    })();

    const rasterTask = (async () => {
      try {
        const result = await fetchRaster(query);
        setRasterResult(result);
      } catch (err) {
        setRasterError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setRasterLoading(false);
      }
    })();

    await Promise.all([statsTask, rasterTask]);
  }

  const availableVariables =
    ingestedResult?.metadata?.variables?.filter((v) => v !== "l2_flags") ?? [];

  const supportsTemporalFilter = ingestedResult?.metadata?.structure === "flat_grid";

  const spatialBounds: SpatialBounds | null = useMemo(() => {
    if (!ingestedResult?.metadata?.lat_range || !ingestedResult?.metadata?.lon_range) {
      return null;
    }
    return {
      latRange: ingestedResult.metadata.lat_range,
      lonRange: ingestedResult.metadata.lon_range,
    };
  }, [ingestedResult]);
  
  const hasFile = !!ingestedFilePath && availableVariables.length > 0;
  
  // Phase B: valid date range for the currently loaded file, sourced
  // from IngestionResult.metadata.time_steps (already available, no
  // backend call needed) — shown next to the date fields so the user
  // knows what range is actually queryable before typing a date that'll
  // return "no time steps in range." Only meaningful for flat-grid files
  // with a time dimension; batch-mode (multi-file directory) range
  // scanning is deferred (Phase D) since it needs a new backend scan,
  // not just existing single-file metadata.
  const validDateRange = useMemo(() => {
    const steps = ingestedResult?.metadata?.time_steps;
    if (!steps || steps.length === 0) return null;
    const sorted = [...steps].sort();
    const trim = (s: string) => (s.length > 10 ? s.slice(0, 10) : s);
    return { min: trim(sorted[0]), max: trim(sorted[sorted.length - 1]) };
  }, [ingestedResult]);

  const MODE_LABELS: Record<Mode, string> = {
    stats: "Query",
    timeseries: "Time Series",
    histogram: "Histogram",
    scatter: "Scatter",
  };

  return (
    <main className="container">
      <h1>OC-ECV Local Engine</h1>

      {!ingestedFilePath ? (
        <>
          <h2>File Ingestion</h2>
          <FileUploader onIngested={handleIngested} />
        </>
      ) : (
        <div className="loaded-file-bar">
          <span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <strong>{ingestedResult?.file_name ?? ingestedFilePath}</strong>
          </span>
          <button type="button" onClick={handleChangeFile}>
            Change file
          </button>
        </div>
      )}

      {hasFile && (
        <div className="app-shell">
          <aside className="sidebar">
            <div className="mode-tabs">
              {(Object.keys(MODE_LABELS) as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={activeMode === m ? "mode-tab active" : "mode-tab"}
                  onClick={() => setActiveMode(m)}
                >
                  {MODE_LABELS[m]}
                </button>
              ))}
            </div>

            {/* All four panels stay mounted at all times (Option A) —
                switching tabs only toggles visibility via CSS, so each
                panel's internal form state (bbox, variable, etc.)
                survives tab switching independently. Only a genuine
                file change (key changes below) remounts and resets
                them. */}
            <div className={activeMode === "stats" ? "sidebar-panel-item" : "sidebar-panel-item hidden"}>
              <ParameterSelector
                key={`params-${ingestedFilePath}`}
                filePath={ingestedFilePath!}
                availableVariables={availableVariables}
                supportsTemporalFilter={supportsTemporalFilter}
                onSubmit={handleQuerySubmit}
                bbox={bboxByMode.stats}
                onBboxChange={setBboxForMode("stats")}
                validDateRange={validDateRange}
              />
            </div>
            <div className={activeMode === "timeseries" ? "sidebar-panel-item" : "sidebar-panel-item hidden"}>
              <TimeSeriesPanel
                key={`timeseries-${ingestedFilePath}`}
                filePath={ingestedFilePath!}
                availableVariables={availableVariables}
                supportsWithinFile={supportsTemporalFilter}
                onResult={setTsResult}
                bbox={bboxByMode.timeseries}
                onBboxChange={setBboxForMode("timeseries")}
                validDateRange={validDateRange}
              />
            </div>
            <div className={activeMode === "histogram" ? "sidebar-panel-item" : "sidebar-panel-item hidden"}>
              <HistogramPanel
                key={`histogram-${ingestedFilePath}`}
                filePath={ingestedFilePath!}
                availableVariables={availableVariables}
                onResult={setHistResult}
                bbox={bboxByMode.histogram}
                onBboxChange={setBboxForMode("histogram")}
              />
            </div>
            <div className={activeMode === "scatter" ? "sidebar-panel-item" : "sidebar-panel-item hidden"}>
              <ScatterPanel
                key={`scatter-${ingestedFilePath}`}
                filePath={ingestedFilePath!}
                availableVariables={availableVariables}
                onResult={setScatterResult}
                bbox={bboxByMode.scatter}
                onBboxChange={setBboxForMode("scatter")}
              />
            </div>
          </aside>

          <section className="main-area">
             {activeMode === "stats" && (
              <div className="map-controls">
                <label htmlFor="colormap-select">Colormap:</label>
                <select
                  id="colormap-select"
                  value={colormap}
                  onChange={(e) => setColormap(e.target.value as ColormapName)}
                >
                  {COLORMAP_NAMES.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>

                <label htmlFor="opacity-slider">Opacity:</label>
                <OpacitySlider
                  value={Math.round(opacity * 100)}
                  onChange={(v) => setOpacity(v / 100)}
                />
                <span className="opacity-readout">{Math.round(opacity * 100)}%</span>
                {rasterLoading && <span className="inline-status">Loading raster…</span>}
                {rasterError && <span className="inline-error">⚠ {rasterError}</span>}
              </div>
            )}

            <MapView
              bbox={bboxByMode[activeMode]}
              onBboxChange={setBboxForMode(activeMode)}
              spatialBounds={spatialBounds}
              // Raster overlay is only meaningful for the Query tab's
              // single-snapshot pixel-value visualization — Time
              // Series/Histogram/Scatter each have their own bbox
              // (already shown correctly) but no single raster that
              // represents "this tab's result," so showing the Query
              // tab's stale raster there was actively misleading
              // (wrong variable, wrong bbox). Hidden on other tabs
              // rather than fetched separately for each, since none of
              // those analysis types map onto a single colored raster
              // image the way a Giovanni-style map output does.
              rasterResult={activeMode === "stats" ? rasterResult : null}
              colormap={colormap}
              opacity={opacity}
            />
            {activeMode === "stats" && rasterResult && (
              <ColorLegend
                colormap={colormap}
                valueMin={rasterResult.valueMin}
                valueMax={rasterResult.valueMax}
                variable={queriedVariable ?? undefined}
              />
            )}

            <div className="results-area">
              {activeMode === "stats" && (
                <>
                  {statsLoading && <p className="status-line">Computing statistics…</p>}
                  {statsError && <div className="error-panel">⚠ {statsError}</div>}
                  {statsResult && !statsError && (
                    <div className="stats-panel">
                      <h3>
                        Statistics: {statsResult.variable} ({statsResult.file_name})
                      </h3>
                      <p>
                        <strong>Valid pixels:</strong> {statsResult.valid_pixel_count} /{" "}
                        {statsResult.total_pixel_count} (
                        {((statsResult.valid_fraction ?? 0) * 100).toFixed(1)}%)
                      </p>
                      {statsResult.mean !== null && statsResult.mean !== undefined ? (
                        <>
                          <p><strong>Mean:</strong> {statsResult.mean.toFixed(4)}</p>
                          <p><strong>Min:</strong> {statsResult.min?.toFixed(4)}</p>
                          <p><strong>Max:</strong> {statsResult.max?.toFixed(4)}</p>
                          <p><strong>Std Dev:</strong> {statsResult.std?.toFixed(4)}</p>
                        </>
                      ) : (
                        <p>No valid pixels in this region — statistics unavailable.</p>
                      )}
                    </div>
                  )}
                </>
              )}

              {activeMode === "timeseries" && tsResult && (
                <TimeSeriesChart
                  data={tsResult.data}
                  variable={tsResult.variable}
                  title={tsResult.title}
                />
              )}

              {activeMode === "histogram" && histResult && (
                <HistogramChart data={histResult} variable={histResult.variable} />
              )}

              {activeMode === "scatter" && scatterResult && (
                <ScatterChart data={scatterResult} />
              )}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

export default App;