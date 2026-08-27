import { useState } from "react";
import "../ExportButton/ExportButton.css";

interface GeoExportButtonProps {
  onExport: () => Promise<void>;
  label?: string;
}

/**
 * Day 38: single-button georeferenced export — no format selector,
 * since format isn't a user choice here (GeoTIFF vs. NetCDF is
 * determined by file structure, not requested). Mirrors
 * RawExportButton.tsx's busy/error handling exactly, minus the <select>.
 */
export default function GeoExportButton({
  onExport,
  label = "Export GeoTIFF/NetCDF",
}: GeoExportButtonProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    try {
      await onExport();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="export-button-group">
      <button onClick={handleClick} disabled={busy}>
        {busy ? "Exporting…" : label}
      </button>
      {error && <span className="export-error">{error}</span>}
    </div>
  );
}