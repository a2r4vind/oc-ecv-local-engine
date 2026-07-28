import { useEffect, useState } from "react";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { open } from "@tauri-apps/plugin-dialog";
import { ingestFile, type IngestionResult } from "../../services/backendApi";
import "./FileUploader.css";

interface FileUploaderProps {
  onIngested?: (filePath: string, result: IngestionResult) => void;
}

export default function FileUploader({ onIngested }: FileUploaderProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Tauri's native drag-drop event gives real filesystem paths for
  // dropped files — unlike the browser's sandboxed HTML5 drag-drop API,
  // which only exposes an opaque blob with no usable path.
  useEffect(() => {
    const unlistenPromise = getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type === "over") {
        setIsDragOver(true);
      } else if (event.payload.type === "drop") {
        setIsDragOver(false);
        const paths = event.payload.paths;
        if (paths && paths.length > 0) {
          handleIngest(paths[0]);
        }
      } else if (event.payload.type === "leave") {
        setIsDragOver(false);
      }
    });

    return () => {
      unlistenPromise.then((unlisten) => unlisten());
    };
  }, []);

  async function handleIngest(filePath: string) {
    setLoading(true);
    setErrorMsg(null);
    setResult(null);
    try {
      const res = await ingestFile(filePath);
      if (res.error) {
        setErrorMsg(res.error);
      } else {
        setResult(res);
        onIngested?.(filePath, res);
      }
    } catch (err) {
      setErrorMsg(
        err instanceof Error
          ? `Could not reach backend: ${err.message}`
          : "Unknown error contacting backend"
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleBrowseClick() {
    const selected = await open({
      multiple: false,
      filters: [{ name: "NetCDF/HDF/GeoTIFF", extensions: ["nc", "hdf", "h5", "tif", "tiff"] }],
    });
    if (typeof selected === "string") {
      handleIngest(selected);
    }
  }

  return (
    <div className="file-uploader">
      <div className={`drop-zone ${isDragOver ? "drag-over" : ""}`}>
        <p>Drag and drop a NetCDF/HDF/GeoTIFF file here</p>
        <p className="drop-zone-or">or</p>
        <button onClick={handleBrowseClick}>Browse Files</button>
      </div>

      {loading && <p className="status-line">Parsing file…</p>}

      {errorMsg && <div className="error-box">⚠ {errorMsg}</div>}

      {result && !errorMsg && (
        <div className="result-panel">
          <h3>{result.file_name}</h3>
          <p>
            <strong>Structure:</strong> {result.metadata?.structure}
          </p>
          <p>
            <strong>Dimensions:</strong>{" "}
            {result.metadata &&
              Object.entries(result.metadata.dimensions)
                .map(([k, v]) => `${k}: ${v}`)
                .join(", ")}
          </p>
          <p>
            <strong>Variables:</strong> {result.metadata?.variables.join(", ")}
          </p>
          {result.metadata?.lat_range && (
            <p>
              <strong>Spatial bounds:</strong> lat{" "}
              {result.metadata.lat_range[0].toFixed(2)} to{" "}
              {result.metadata.lat_range[1].toFixed(2)}, lon{" "}
              {result.metadata.lon_range?.[0].toFixed(2)} to{" "}
              {result.metadata.lon_range?.[1].toFixed(2)}
            </p>
          )}
          <p>
            <strong>Chlorophyll variables:</strong>{" "}
            {result.ecv_variables?.chlorophyll.join(", ") || "none found"}
          </p>
          <p>
            <strong>Reflectance variables:</strong>{" "}
            {result.ecv_variables?.reflectance.join(", ") || "none found"}
          </p>
          <p className={result.validation?.valid ? "valid-tag" : "invalid-tag"}>
            {result.validation?.valid ? "✓ Valid" : "✗ Invalid"}
          </p>
          {result.validation?.errors && result.validation.errors.length > 0 && (
            <ul className="issue-list errors">
              {result.validation.errors.map((e) => (
                <li key={e.code}>{e.message}</li>
              ))}
            </ul>
          )}
          {result.validation?.warnings && result.validation.warnings.length > 0 && (
            <ul className="issue-list warnings">
              {result.validation.warnings.map((w) => (
                <li key={w.code}>{w.message}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}