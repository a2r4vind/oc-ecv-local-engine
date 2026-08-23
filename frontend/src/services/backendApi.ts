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

export interface RasterBitmapResult {
  type: "bitmap";
  imageBitmap: ImageBitmap;
  bounds: [number, number, number, number]; // west, south, east, north
  valueMin: number;
  valueMax: number;
  gridShape: [number, number];
}

export interface RasterPointsResult {
  type: "points";
  lon: Float32Array;
  lat: Float32Array;
  value: Float32Array; // normalized 0-1
  valueMin: number;
  valueMax: number;
  pointCount: number;
}

export type RasterResult = RasterBitmapResult | RasterPointsResult;

export async function fetchRaster(query: StatsQuery): Promise<RasterResult> {
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

  const res = await fetch(`${BASE_URL}/raster?${params.toString()}`);
  if (!res.ok) {
    let message = `Backend returned status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson?.error) message = errJson.error;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new Error(message);
  }

  const rasterType = res.headers.get("X-Raster-Type");
  const valueMin = parseFloat(res.headers.get("X-Value-Min") ?? "0");
  const valueMax = parseFloat(res.headers.get("X-Value-Max") ?? "1");

  if (rasterType === "bitmap") {
    const boundsHeader = res.headers.get("X-Bounds") ?? "";
    const bounds = boundsHeader.split(",").map(Number) as [number, number, number, number];
    const shapeHeader = res.headers.get("X-Grid-Shape") ?? "";
    const gridShape = shapeHeader.split(",").map(Number) as [number, number];

    const blob = await res.blob();
    const imageBitmap = await createImageBitmap(blob);

    return { type: "bitmap", imageBitmap, bounds, valueMin, valueMax, gridShape };
  }

  if (rasterType === "points") {
    const pointCount = parseInt(res.headers.get("X-Point-Count") ?? "0", 10);
    const buffer = await res.arrayBuffer();

    // Binary layout from raster.py: [uint32 count][float32 lon * N]
    // [float32 lat * N][float32 normalized_value * N]. Relies on NumPy's
    // .tobytes() (little-endian on x86_64) matching JS typed arrays'
    // native byte order (also little-endian on x86_64 Chromium/
    // WebKit) — true for this project's target platform, flagged here
    // explicitly rather than left implicit.
    const HEADER_BYTES = 4;
    const lon = new Float32Array(buffer, HEADER_BYTES, pointCount);
    const lat = new Float32Array(buffer, HEADER_BYTES + pointCount * 4, pointCount);
    const value = new Float32Array(buffer, HEADER_BYTES + pointCount * 8, pointCount);

    return { type: "points", lon, lat, value, valueMin, valueMax, pointCount };
  }

  throw new Error(`Unexpected X-Raster-Type header: ${rasterType}`);
}

export interface WithinFileTimeSeriesEntry {
  time: string;
  total_pixel_count?: number;
  valid_pixel_count?: number;
  valid_fraction?: number;
  mean: number | null;
  min?: number | null;
  max?: number | null;
  std?: number | null;
}

export interface WithinFileTimeSeriesResult {
  file_name?: string;
  variable?: string;
  entries: WithinFileTimeSeriesEntry[];
  error?: string;
}

export async function fetchTimeseriesWithinFile(params: {
  filePath: string;
  variable: string;
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
  startDate?: string;
  endDate?: string;
}): Promise<WithinFileTimeSeriesResult> {
  const query = new URLSearchParams({
    path: params.filePath,
    variable: params.variable,
    lat_min: String(params.latMin),
    lat_max: String(params.latMax),
    lon_min: String(params.lonMin),
    lon_max: String(params.lonMax),
  });
  if (params.startDate) query.set("start_date", params.startDate);
  if (params.endDate) query.set("end_date", params.endDate);

  const res = await fetch(`${BASE_URL}/timeseries-within-file?${query.toString()}`);
  if (!res.ok) {
    throw new Error(`Backend returned status ${res.status}`);
  }
  return res.json();
}

export interface BatchTimeseriesEntry {
  file: string;
  mean?: number | null;
  min?: number | null;
  max?: number | null;
  std?: number | null;
  valid_fraction?: number;
  skipped?: boolean;
  reason?: string;
  error?: string;
}

export interface BatchTimeseriesResult {
  variable?: string;
  file_count?: number;
  timeseries: BatchTimeseriesEntry[];
  error?: string;
}

export async function fetchBatchTimeseries(params: {
  directory: string;
  variable: string;
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
  startDate: string; // required — Day 17's filter_files_by_date_range has
  // no None-guard on start/end date, so these can't be left optional here
  // the way /stats and /timeseries-within-file allow.
  endDate: string;
}): Promise<BatchTimeseriesResult> {
  const query = new URLSearchParams({
    directory: params.directory,
    variable: params.variable,
    lat_min: String(params.latMin),
    lat_max: String(params.latMax),
    lon_min: String(params.lonMin),
    lon_max: String(params.lonMax),
    start_date: params.startDate,
    end_date: params.endDate,
  });

  const res = await fetch(`${BASE_URL}/batch-timeseries?${query.toString()}`);
  if (!res.ok) {
    throw new Error(`Backend returned status ${res.status}`);
  }
  return res.json();
}

export interface HistogramResult {
  file_name?: string;
  variable?: string;
  bin_edges: number[];
  counts: number[];
  valid_pixel_count?: number;
  mean?: number;
  std?: number;
  error?: string;
}

export interface HistogramQuery {
  filePath: string;
  variable: string;
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
  startDate?: string;
  endDate?: string;
  qualityFlags?: string[];
  bins?: number;
}

export async function fetchHistogram(query: HistogramQuery): Promise<HistogramResult> {
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
  if (query.bins) params.set("bins", String(query.bins));

  const res = await fetch(`${BASE_URL}/histogram?${params.toString()}`);
  if (!res.ok) {
    let message = `Backend returned status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson?.error) message = errJson.error;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new Error(message);
  }
  return res.json();
}

export interface ScatterResult {
  file_name?: string;
  variable_x?: string;
  variable_y?: string;
  x: number[];
  y: number[];
  total_pair_count?: number;
  returned_pair_count?: number;
  correlation?: number | null;
  error?: string;
}

export interface ScatterQuery {
  filePath: string;
  variableX: string;
  variableY: string;
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
  startDate?: string;
  endDate?: string;
  qualityFlags?: string[];
}

export async function fetchScatter(query: ScatterQuery): Promise<ScatterResult> {
  const params = new URLSearchParams({
    path: query.filePath,
    variable_x: query.variableX,
    variable_y: query.variableY,
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

  const res = await fetch(`${BASE_URL}/scatter?${params.toString()}`);
  if (!res.ok) {
    let message = `Backend returned status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson?.error) message = errJson.error;
    } catch {
      // response wasn't JSON — keep the generic message
    }
    throw new Error(message);
  }
  return res.json();
}

export interface DateCoverageFileEntry {
  file_name: string;
  has_time_info: boolean;
  start?: string;
  end?: string;
  source?: string;
  skip_reason?: string;
}

export interface DateCoverageResult {
  directory: string;
  total_files: number;
  files_with_time_info: number;
  files_without_time_info: number;
  overall_start: string | null;
  overall_end: string | null;
  per_file: DateCoverageFileEntry[];
}

export async function scanDateCoverage(directory: string): Promise<DateCoverageResult> {
  const res = await fetch(`${BASE_URL}/batch-date-coverage?directory=${encodeURIComponent(directory)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}