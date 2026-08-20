// Normalizes the two distinct backend time-series shapes — Day 25's
// /timeseries-within-file (single file, multiple time steps) and Day 17's
// /batch-timeseries (multiple files, one time step each) — into one
// common structure, so a single chart component can render either
// without caring which source it came from. Anomaly (deviation from the
// series' own mean) is computed here, client-side, rather than
// duplicating the same subtract-the-mean logic in two backend functions.

export interface TimeSeriesPoint {
  time: string;
  value: number | null;
  anomaly: number | null;
}

export interface NormalizedTimeSeries {
  points: TimeSeriesPoint[];
  seriesMean: number | null;
}

interface WithinFileEntry {
  time: string;
  mean: number | null;
}
interface WithinFileResult {
  // file_name/variable are optional here to match backendApi.ts's actual
  // WithinFileTimeSeriesResult shape (the source of truth for what the
  // FastAPI /timeseries-within-file endpoint can return) — neither field
  // is actually read below, this type only exists to describe what
  // normalizeWithinFileResult needs from its input, not to enforce
  // fields the backend doesn't guarantee.
  file_name?: string;
  variable?: string;
  entries: WithinFileEntry[];
  error?: string;
}
interface BatchTimeseriesEntry {
  file: string;
  mean?: number | null;
  skipped?: boolean;
  error?: string;
}
interface BatchTimeseriesResult {
  // Same reasoning as WithinFileResult above — matches backendApi.ts's
  // actual BatchTimeseriesResult shape; variable/file_count aren't read
  // by normalizeBatchResult below.
  variable?: string;
  file_count?: number;
  timeseries: BatchTimeseriesEntry[];
  error?: string;
}

function computeAnomalies(
  rawPoints: { time: string; value: number | null }[]
): NormalizedTimeSeries {
  const validValues = rawPoints
    .map((p) => p.value)
    .filter((v): v is number => v !== null && Number.isFinite(v));

  const seriesMean =
    validValues.length > 0
      ? validValues.reduce((a, b) => a + b, 0) / validValues.length
      : null;

  const points: TimeSeriesPoint[] = rawPoints.map((p) => ({
    time: p.time,
    value: p.value,
    anomaly:
      p.value !== null && seriesMean !== null ? p.value - seriesMean : null,
  }));

  return { points, seriesMean };
}

export function normalizeWithinFileResult(
  result: WithinFileResult
): NormalizedTimeSeries {
  const rawPoints = result.entries.map((e) => ({
    time: e.time,
    value: e.mean,
  }));
  return computeAnomalies(rawPoints);
}

export function normalizeBatchResult(
  result: BatchTimeseriesResult
): NormalizedTimeSeries {
  // Batch entries include skipped (no bbox overlap) and errored files —
  // both are excluded from the plotted series rather than shown as
  // false zero/null points, consistent with Day 17's established
  // distinction between "no data" and "genuine failure".
  const rawPoints = result.timeseries
    .filter((e) => !e.skipped && !e.error)
    .map((e) => ({
      time: e.file, // real MODIS filenames embed an ISO-ordered timestamp,
      // so filename sort order is also chronological order.
      value: e.mean ?? null,
    }));
  return computeAnomalies(rawPoints);
}