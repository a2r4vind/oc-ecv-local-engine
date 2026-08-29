import { useEffect, useState } from "react";
import { fetchHistory, type HistoryEntry } from "../../services/backendApi";
import "./HistoryPanel.css";

interface HistoryPanelProps {
  onReload: (entry: HistoryEntry) => void | Promise<void>;
  // Bumped by the parent after a successful reload, so a freshly-run
  // query shows up at the top of the list without requiring the user
  // to manually refresh — same "reflect the latest state" expectation
  // as every other panel in this app.
  refreshToken?: number;
}

export default function HistoryPanel({ onReload, refreshToken }: HistoryPanelProps) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadingKey, setReloadingKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchHistory(50, 0)
      .then((res) => {
        if (cancelled) return;
        if (res.error) {
          setError(res.error);
        } else {
          setEntries(res.entries);
          setTotal(res.total);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? `Could not reach backend: ${err.message}` : "Unknown error"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  async function handleClick(entry: HistoryEntry) {
    setReloadingKey(entry.cache_key);
    try {
      await onReload(entry);
    } finally {
      setReloadingKey(null);
    }
  }

  return (
    <div className="history-panel">
      <h2>Query History</h2>
      {loading && <p className="timeseries-note">Loading history…</p>}
      {error && <div className="history-error">⚠ {error}</div>}
      {!loading && !error && entries.length === 0 && (
        <p className="timeseries-note">No past queries yet. Run a query to see it here.</p>
      )}
      {!loading && !error && entries.length > 0 && (
        <>
          <p className="history-count">
            Showing {entries.length} of {total}
          </p>
          <ul className="history-list">
            {entries.map((entry) => (
              <li key={entry.cache_key} className="history-entry">
                <div className="history-entry-main">
                  <strong>{entry.variable}</strong>
                  <span className="history-file-name">{entry.file_name}</span>
                </div>
                <div className="history-entry-detail">
                  bbox [{entry.lat_min.toFixed(2)}, {entry.lat_max.toFixed(2)},{" "}
                  {entry.lon_min.toFixed(2)}, {entry.lon_max.toFixed(2)}]
                  {entry.start_date && entry.end_date && (
                    <> · {entry.start_date} → {entry.end_date}</>
                  )}
                </div>
                <div className="history-entry-meta">
                  <span>{new Date(entry.created_at).toLocaleString()}</span>
                  <span>{entry.hit_count} hit{entry.hit_count === 1 ? "" : "s"}</span>
                </div>
                <button
                  type="button"
                  disabled={reloadingKey === entry.cache_key}
                  onClick={() => handleClick(entry)}
                >
                  {reloadingKey === entry.cache_key ? "Reloading…" : "Reload"}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}