import { useState } from "react";
import type { RawExportFormat } from "../../services/backendApi";
import "../ExportButton/ExportButton.css";

interface RawExportButtonProps {
  onExport: (format: RawExportFormat) => Promise<void>;
  label?: string;
}

export default function RawExportButton({
  onExport,
  label = "Export Data",
}: RawExportButtonProps) {
  const [format, setFormat] = useState<RawExportFormat>("csv");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    try {
      await onExport(format);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="export-button-group">
      <select
        value={format}
        onChange={(e) => setFormat(e.target.value as RawExportFormat)}
        disabled={busy}
        aria-label="Raw data export format"
      >
        <option value="csv">CSV</option>
        <option value="bin">Binary (.bin)</option>
      </select>
      <button onClick={handleClick} disabled={busy}>
        {busy ? "Exporting…" : label}
      </button>
      {error && <span className="export-error">{error}</span>}
    </div>
  );
}