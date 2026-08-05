import { useState } from "react";
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
  type IngestionResult,
  type StatsResult,
} from "./services/backendApi";
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

  async function greet() {
    setGreetMsg(await invoke("greet", { name }));
  }

  function handleIngested(filePath: string, result: IngestionResult) {
    setIngestedFilePath(filePath);
    setIngestedResult(result);
    setStatsResult(null);
    setStatsError(null);
    setMapBbox(null);
  }

  async function handleQuerySubmit(params: QueryParams) {
    setStatsLoading(true);
    setStatsResult(null);
    setStatsError(null);

    try {
      const result = await computeStats({
        filePath: params.filePath,
        variable: params.variable,
        latMin: params.latMin,
        latMax: params.latMax,
        lonMin: params.lonMin,
        lonMax: params.lonMax,
        startDate: params.startDate,
        endDate: params.endDate,
      });

      if (result.error) {
        setStatsError(result.error);
      } else {
        setStatsResult(result);
      }
    } catch (err) {
      setStatsError(
        err instanceof Error ? `Could not reach backend: ${err.message}` : "Unknown error"
      );
    } finally {
      setStatsLoading(false);
    }
  }

  const availableVariables =
    ingestedResult?.metadata?.variables?.filter((v) => v !== "l2_flags") ?? [];

  const supportsTemporalFilter = ingestedResult?.metadata?.structure === "flat_grid";
  
  const spatialBounds: SpatialBounds | null =
    ingestedResult?.metadata?.lat_range && ingestedResult?.metadata?.lon_range
      ? {
          latRange: ingestedResult.metadata.lat_range,
          lonRange: ingestedResult.metadata.lon_range,
        }
      : null;

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
          <MapView bbox={mapBbox} spatialBounds={spatialBounds} />
          
          <h2>Query Parameters</h2>
          <ParameterSelector
            key={ingestedFilePath}
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