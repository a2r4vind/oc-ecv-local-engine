// Thin wrapper around the local FastAPI sidecar's HTTP endpoints.
// Kept separate from components so the base URL/port lives in one place.

const BASE_URL = "http://127.0.0.1:5321";

export interface IngestionResult {
  file_name?: string;
  metadata?: {
    structure: string;
    dimensions: Record<string, number>;
    variables: string[];
    coordinates: string[];
    lat_range?: [number, number];
    lon_range?: [number, number];
    time_steps?: string[];
    num_time_steps?: number;
    global_attrs: Record<string, unknown>;
  };
  ecv_variables?: {
    chlorophyll: string[];
    reflectance: string[];
  };
  validation?: {
    valid: boolean;
    errors: { code: string; message: string }[];
    warnings: { code: string; message: string }[];
  };
  error?: string;
}

export interface StatsResult {
  total_pixel_count?: number;
  valid_pixel_count?: number;
  valid_fraction?: number;
  mean?: number | null;
  min?: number | null;
  max?: number | null;
  std?: number | null;
  file_name?: string;
  variable?: string;
  bbox?: { lat_min: number; lat_max: number; lon_min: number; lon_max: number };
  date_range?: { start: string; end: string };
  quality_flags_masked?: string[];
  error?: string;
}

export interface StatsQuery {
  filePath: string;
  variable: string;
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
  startDate?: string;
  endDate?: string;
  qualityFlags?: string[];
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function ingestFile(filePath: string): Promise<IngestionResult> {
  const res = await fetch(
    `${BASE_URL}/ingest?path=${encodeURIComponent(filePath)}`
  );
  if (!res.ok) {
    throw new Error(`Backend returned status ${res.status}`);
  }
  return res.json();
}

export async function computeStats(query: StatsQuery): Promise<StatsResult> {
  const params = new URLSearchParams({
    path: query.filePath,
    variable: query.variable,
    lat_min: String(query.latMin),
    lat_max: String(query.latMax),
    lon_min: String(query.lonMin),
    lon_max: String(query.lonMax),
  });

  if (query.startDate) params.set("start_date", query.startDate);
  if (query.endDate) params.set("end_date", query.endDate);
  if (query.qualityFlags && query.qualityFlags.length > 0) {
    params.set("quality_flags", query.qualityFlags.join(","));
  }

  const res = await fetch(`${BASE_URL}/stats?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Backend returned status ${res.status}`);
  }
  return res.json();
}