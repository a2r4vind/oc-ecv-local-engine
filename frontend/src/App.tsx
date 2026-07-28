import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/core";
import FileUploader from "./components/FileUploader/FileUploader";
import ParameterSelector, {
  type QueryParams,
} from "./components/ParameterSelector/ParameterSelector";
import type { IngestionResult } from "./services/backendApi";
import "./App.css";

function App() {
  const [greetMsg, setGreetMsg] = useState("");
  const [name, setName] = useState("");

  const [ingestedFilePath, setIngestedFilePath] = useState<string | null>(null);
  const [ingestedResult, setIngestedResult] = useState<IngestionResult | null>(null);
  const [lastQuery, setLastQuery] = useState<QueryParams | null>(null);

  async function greet() {
    setGreetMsg(await invoke("greet", { name }));
  }

  function handleIngested(filePath: string, result: IngestionResult) {
    setIngestedFilePath(filePath);
    setIngestedResult(result);
    setLastQuery(null);
  }

  function handleQuerySubmit(params: QueryParams) {
    // Day 15 will replace this with an actual call to a new backend
    // statistics endpoint. For now, Days 12-14 scope is just building
    // and validating the UI's ability to assemble a well-formed query.
    setLastQuery(params);
  }

  const availableVariables =
    ingestedResult?.metadata?.variables?.filter((v) => v !== "l2_flags") ?? [];

  const supportsTemporalFilter = ingestedResult?.metadata?.structure === "flat_grid";

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
          <h2>Query Parameters</h2>
          <ParameterSelector
            key={ingestedFilePath}
            filePath={ingestedFilePath}
            availableVariables={availableVariables}
            supportsTemporalFilter={supportsTemporalFilter}
            onSubmit={handleQuerySubmit}
          />
        </>
      )}

      {lastQuery && (
        <div style={{ maxWidth: 640, margin: "0 auto", textAlign: "left" }}>
          <h3>Assembled Query (Day 15 will send this to the backend)</h3>
          <pre
            style={{
              background: "#f5f5f5",
              padding: "1rem",
              borderRadius: 6,
              fontSize: "0.85rem",
              overflowX: "auto",
            }}
          >
            {JSON.stringify(lastQuery, null, 2)}
          </pre>
        </div>
      )}
    </main>
  );
}

export default App;