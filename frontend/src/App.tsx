import { useState, useMemo } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/core";
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
} from "./services/backendApi";
import { COLORMAP_NAMES, type ColormapName } from "./utils/colormaps";
import ColorLegend from "./components/ColorLegend/ColorLegend";
import OpacitySlider from "./components/OpacitySlider/OpacitySlider";
import TimeSeriesPanel from "./components/TimeSeriesPanel/TimeSeriesPanel";
import HistogramPanel from "./components/HistogramPanel/HistogramPanel";
import ScatterPanel from "./components/ScatterPanel/ScatterPanel";
import "./App.css";

function App() {
  const [greetMsg, setGreetMsg] = useState("");
  const [name, setName] = useState("");

  const [ingestedFilePath, setIngestedFilePath] = useState<string | null>(null);
  const [ingestedResult, setIngestedResult] = useState<IngestionResult | null>(null);
  const [mapBbox, setMapBbox] = useState<MapBbox | null>(null);
  
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsResult, setStatsResult] = useState<StatsResult | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [rasterLoading, setRasterLoading] = useState(false);
  const [rasterResult, setRasterResult] = useState<RasterResult | null>(null);
  const [rasterError, setRasterError] = useState<string | null>(null);
  const [colormap, setColormap] = useState<ColormapName>("viridis");
  const [opacity, setOpacity] = useState(1);
  const [queriedVariable, setQueriedVariable] = useState<string | null>(null);

  async function greet() {
    setGreetMsg(await invoke("greet", { name }));
  }

  function handleIngested(filePath: string, result: IngestionResult) {
    setIngestedFilePath(filePath);
    setIngestedResult(result);
    setStatsResult(null);
    setStatsError(null);
    setMapBbox(null);
    setRasterResult(null);
    setRasterError(null);
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

    // Fired concurrently, independent loading/error states — a raster
    // failure (e.g. a genuinely empty region) shouldn't block the stats
    // panel from displaying, and vice versa.
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
  
  // Memoized so this object reference only changes when a NEW file is
  // actually ingested — not on every unrelated App re-render (opacity
  // drag, colormap switch, bbox keystroke). Without this, MapView's
  // auto-zoom effect (keyed on this object) re-fires on every such
  // render and silently resets any manual pan/zoom back to the file's
  // full extent, since a new object literal on every render looks like
  // "changed" to React's reference-based dependency comparison even
  // when the underlying lat/lon values are identical.
  const spatialBounds: SpatialBounds | null = useMemo(() => {
    if (!ingestedResult?.metadata?.lat_range || !ingestedResult?.metadata?.lon_range) {
      return null;
    }
    return {
      latRange: ingestedResult.metadata.lat_range,
      lonRange: ingestedResult.metadata.lon_range,
    };
  }, [ingestedResult]);
  

  return (
    <main className="container">
      <h1>Welcome to Tauri + React</h1>
      <div className="row">
        <a href="https://vite.dev" target="_blank">
          <img src="/vite.svg" className="logo vite" alt="Vite logo" />
        </a>
        <a href="https://tauri.app" target="_blank">
          <img src="/tauri.svg" className="logo tauri" alt="Tauri logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <p>Click on the Tauri, Vite, and React logos to learn more.</p>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          greet();
        }}
      >
        <input
          id="greet-input"
          onChange={(e) => setName(e.currentTarget.value)}
          placeholder="Enter a name..."
        />
        <button type="submit">Greet</button>
      </form>
      <p>{greetMsg}</p>

      <hr style={{ margin: "2rem 0" }} />

      <h2>OC-ECV File Ingestion</h2>
      <FileUploader onIngested={handleIngested} />

      {ingestedFilePath && availableVariables.length > 0 && (
        <>
          <h2>Map</h2>
          <div style={{ maxWidth: 640, margin: "0 auto 0.5rem", textAlign: "left" }}>
            <label htmlFor="colormap-select" style={{ marginRight: "0.5rem" }}>
              Colormap:
            </label>
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
            
            <label htmlFor="opacity-slider" style={{ marginLeft: "1rem", marginRight: "0.5rem" }}>
              Opacity:
            </label>
            <OpacitySlider
              value={Math.round(opacity * 100)}
              onChange={(v) => setOpacity(v / 100)}
            />
            <span style={{ marginLeft: "0.35rem" }}>{Math.round(opacity * 100)}%</span>
            {rasterLoading && <span style={{ marginLeft: "0.75rem" }}>Loading raster…</span>}
            {rasterError && (
              <span style={{ marginLeft: "0.75rem", color: "#b91c1c" }}>⚠ {rasterError}</span>
            )}
          </div>
          <MapView
            bbox={mapBbox}
            spatialBounds={spatialBounds}
            rasterResult={rasterResult}
            colormap={colormap}
            opacity={opacity}
          />
          {rasterResult && (
            <ColorLegend
              colormap={colormap}
              valueMin={rasterResult.valueMin}
              valueMax={rasterResult.valueMax}
              variable={queriedVariable ?? undefined}
            />
          )}
          
          <TimeSeriesPanel
            key={`timeseries-${ingestedFilePath}`}
            filePath={ingestedFilePath}
            availableVariables={availableVariables}
            defaultBbox={mapBbox}
            supportsWithinFile={supportsTemporalFilter}
          />
          
          <HistogramPanel
            key={`histogram-${ingestedFilePath}`}
            filePath={ingestedFilePath}
            availableVariables={availableVariables}
            defaultBbox={mapBbox}
          />

          <ScatterPanel
            key={`scatter-${ingestedFilePath}`}
            filePath={ingestedFilePath}
            availableVariables={availableVariables}
            defaultBbox={mapBbox}
          />
          
          <h2>Query Parameters</h2>
          <ParameterSelector
            key={`params-${ingestedFilePath}`}
            filePath={ingestedFilePath}
            availableVariables={availableVariables}
            supportsTemporalFilter={supportsTemporalFilter}
            onSubmit={handleQuerySubmit}
            onBboxChange={setMapBbox}
          />
        </>
      )}

      {statsLoading && (
        <p style={{ textAlign: "center" }}>Computing statistics…</p>
      )}

      {statsError && (
        <div
          style={{
            maxWidth: 640,
            margin: "1rem auto",
            padding: "0.75rem 1rem",
            borderRadius: 6,
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            color: "#b91c1c",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            textAlign: "left",
          }}
        >
          ⚠ {statsError}
        </div>
      )}

      {statsResult && !statsError && (
        <div
          style={{
            maxWidth: 640,
            margin: "1rem auto",
            padding: "1rem 1.25rem",
            borderRadius: 8,
            border: "1px solid #ddd",
            textAlign: "left",
          }}
        >
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
    </main>
  );
}

export default App;