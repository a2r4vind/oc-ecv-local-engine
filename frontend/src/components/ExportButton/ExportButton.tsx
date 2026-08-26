import { useState } from "react";
import type { ExportFormat } from "../../utils/mapExport";
import "./ExportButton.css";

interface ExportButtonProps {
  onExport: (format: ExportFormat) => Promise<void>;
  label?: string;
}

export default function ExportButton({ onExport, label = "Export" }: ExportButtonProps) {
  const [format, setFormat] = useState<ExportFormat>("png");
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
        onChange={(e) => setFormat(e.target.value as ExportFormat)}
        disabled={busy}
        aria-label="Export format"
      >
        <option value="png">PNG</option>
        <option value="jpeg">JPEG</option>
      </select>
      <button onClick={handleClick} disabled={busy}>
        {busy ? "Exporting…" : label}
      </button>
      {error && <span className="export-error">{error}</span>}
    </div>
  );
}