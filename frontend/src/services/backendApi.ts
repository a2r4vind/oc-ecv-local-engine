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