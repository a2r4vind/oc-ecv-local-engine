// Colormap stop tables + client-side application, for Day 23's raster
// rendering. The backend (raster.py) deliberately sends raw grayscale
// luminance + alpha, never a baked-in colormap — recoloring happens here,
// entirely client-side, so switching Viridis/Ocean/Jet never requires a
// backend re-fetch (only re-runs this recoloring step against data
// already in memory).

export type ColormapName = "viridis" | "ocean" | "jet";

type Stop = { t: number; color: [number, number, number] };

// Hand-written approximations of standard colormaps (not pulled from a
// dependency — these are small, static RGB stop tables, standard
// practice for this rather than adding a colormap library).
const COLORMAPS: Record<ColormapName, Stop[]> = {
  viridis: [
    { t: 0.0, color: [68, 1, 84] },
    { t: 0.13, color: [72, 40, 120] },
    { t: 0.25, color: [62, 74, 137] },
    { t: 0.38, color: [49, 104, 142] },
    { t: 0.5, color: [38, 130, 142] },
    { t: 0.63, color: [31, 158, 137] },
    { t: 0.75, color: [53, 183, 121] },
    { t: 0.88, color: [109, 205, 89] },
    { t: 1.0, color: [253, 231, 37] },
  ],
  ocean: [
    { t: 0.0, color: [0, 0, 40] },
    { t: 0.15, color: [0, 20, 90] },
    { t: 0.3, color: [0, 60, 140] },
    { t: 0.45, color: [0, 110, 160] },
    { t: 0.6, color: [20, 150, 150] },
    { t: 0.75, color: [80, 190, 160] },
    { t: 0.9, color: [180, 220, 200] },
    { t: 1.0, color: [255, 255, 255] },
  ],
  jet: [
    { t: 0.0, color: [0, 0, 131] },
    { t: 0.125, color: [0, 60, 170] },
    { t: 0.375, color: [5, 255, 255] },
    { t: 0.625, color: [255, 255, 0] },
    { t: 0.875, color: [250, 0, 0] },
    { t: 1.0, color: [128, 0, 0] },
  ],
};

export const COLORMAP_NAMES: ColormapName[] = ["viridis", "ocean", "jet"];

/** Builds a CSS linear-gradient string from a colormap's own stop table,
 * so the legend bar can never visually disagree with what's actually
 * rendered on the map — same source data, different output format. */
export function getGradientCss(name: ColormapName): string {
  const stops = COLORMAPS[name];
  const stopStrings = stops.map(
    (s) => `rgb(${s.color[0]}, ${s.color[1]}, ${s.color[2]}) ${(s.t * 100).toFixed(0)}%`
  );
  return `linear-gradient(to right, ${stopStrings.join(", ")})`;
}

function lerp(a: number, b: number, f: number): number {
  return a + (b - a) * f;
}

/** Looks up an interpolated RGB color for normalized value t (0-1). */
export function getColor(name: ColormapName, t: number): [number, number, number] {
  const stops = COLORMAPS[name];
  const clamped = Math.min(1, Math.max(0, t));

  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    if (clamped >= a.t && clamped <= b.t) {
      const f = b.t === a.t ? 0 : (clamped - a.t) / (b.t - a.t);
      return [
        Math.round(lerp(a.color[0], b.color[0], f)),
        Math.round(lerp(a.color[1], b.color[1], f)),
        Math.round(lerp(a.color[2], b.color[2], f)),
      ];
    }
  }
  return stops[stops.length - 1].color;
}

/**
 * Recolors a decoded grayscale+alpha bitmap (from raster.py's PNG
 * encoding) using the given colormap, entirely client-side. After canvas
 * decoding, the source PNG's LA (luminance, alpha) channels land in the
 * standard RGBA layout with R=G=B=luminance — only R is read here since
 * G and B are identical copies of it.
 *
 * Returns a canvas (not a re-encoded ImageBitmap) since deck.gl's
 * BitmapLayer accepts an HTMLCanvasElement directly as its `image` prop,
 * avoiding an unnecessary extra encode/decode round-trip.
 */
export function recolorBitmap(
  source: ImageBitmap,
  colormap: ColormapName
): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = source.width;
  canvas.height = source.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Could not acquire 2D canvas context for colormap recoloring");
  }

  ctx.drawImage(source, 0, 0);
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;

  for (let i = 0; i < data.length; i += 4) {
    const alpha = data[i + 3];
    if (alpha === 0) continue; // masked pixel — leave fully transparent, skip recoloring
    const luminance = data[i]; // R channel; G/B are identical copies from LA decode
    const [r, g, b] = getColor(colormap, luminance / 255);
    data[i] = r;
    data[i + 1] = g;
    data[i + 2] = b;
    // alpha (data[i + 3]) left unchanged
  }

  ctx.putImageData(imageData, 0, 0);
  return canvas;
}


/**
 * Day 30: decoded raw (denormalized) pixel values for a flat-grid raster,
 * kept separate from recolorBitmap()'s display canvas above. Colormap-
 * independent by design — only needs to be decoded once per raster
 * result, not once per colormap switch, since it's used for hover-
 * tooltip value lookup rather than rendering.
 */
export interface RawBitmapData {
  values: Float32Array; // denormalized; NaN for masked/invalid pixels
  width: number;
  height: number;
}

export function decodeRawBitmapValues(
  source: ImageBitmap,
  valueMin: number,
  valueMax: number
): RawBitmapData {
  const canvas = document.createElement("canvas");
  canvas.width = source.width;
  canvas.height = source.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Could not acquire 2D canvas context for raw value decoding");
  }

  ctx.drawImage(source, 0, 0);
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;
  const values = new Float32Array(canvas.width * canvas.height);

  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    const alpha = data[i + 3];
    if (alpha === 0) {
      values[p] = NaN; // masked pixel — matches recolorBitmap's skip-on-alpha-0 convention
      continue;
    }
    const luminance = data[i]; // R channel; G/B are identical copies from LA decode
    values[p] = valueMin + (luminance / 255) * (valueMax - valueMin);
  }

  return { values, width: canvas.width, height: canvas.height };
}

/**
 * Looks up a raw denormalized value at a given [lon, lat] map coordinate
 * within a decoded bitmap's raw value grid, using the raster's own
 * geographic bounds (the same bounds passed to deck.gl's BitmapLayer).
 * Returns null if the coordinate falls outside the raster's bounds, or
 * lands on a masked/invalid pixel.
 *
 * Row 0 is assumed to be the image's top edge (north), consistent with
 * raster.py's north-up row-orientation handling (Day 23) — this is
 * inferred from the Day 23 report's description, not read directly from
 * raster.py's current source, so verify it live against a real file
 * before trusting it fully.
 */
export function lookupBitmapValue(
  coordinate: [number, number],
  bounds: [number, number, number, number], // west, south, east, north
  raw: RawBitmapData
): number | null {
  const [lon, lat] = coordinate;
  const [west, south, east, north] = bounds;
  if (lon < west || lon > east || lat < south || lat > north) return null;

  const col = Math.min(
    raw.width - 1,
    Math.max(0, Math.floor(((lon - west) / (east - west)) * raw.width))
  );
  const row = Math.min(
    raw.height - 1,
    Math.max(0, Math.floor(((north - lat) / (north - south)) * raw.height))
  );

  const value = raw.values[row * raw.width + col];
  return Number.isNaN(value) ? null : value;
}