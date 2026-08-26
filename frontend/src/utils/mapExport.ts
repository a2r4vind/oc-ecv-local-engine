import type { MapRef } from "react-map-gl/maplibre";

export type ExportFormat = "png" | "jpeg";

interface ExportMapOptions {
  mapRef: React.RefObject<MapRef | null>;
  containerEl: HTMLElement;
  format: ExportFormat;
  scale?: number; // resolution multiplier on top of devicePixelRatio, default 2
  jpegQuality?: number; // 0-1, default 0.92
}

/**
 * Composites MapLibre's base canvas and deck.gl's overlay canvas (two
 * separate <canvas> elements, per Day 22's overlaid interleaved:false
 * decision) onto one offscreen canvas at `scale`x resolution, then
 * encodes to PNG or JPEG.
 *
 * Requires preserveDrawingBuffer: true on the MapLibre Map (see
 * MapView.tsx) or getCanvas() returns a blank buffer.
 */
export async function exportMapToBlob({
  mapRef,
  containerEl,
  format,
  scale = 2,
  jpegQuality = 0.92,
}: ExportMapOptions): Promise<Blob> {
  const maplibreMap = mapRef.current?.getMap();
  if (!maplibreMap) {
    throw new Error("Map is not ready yet");
  }

  // Force a fresh paint immediately before capture, and wait two RAF
  // ticks so the retained buffer reflects the very latest frame rather
  // than racing the render loop.
  maplibreMap.triggerRepaint();
  await new Promise<void>((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  );
  
  const baseCanvas = maplibreMap.getCanvas();
  // deck.gl's MapboxOverlay doesn't expose its canvas through a public
  // ref — locate it via the DOM instead. NOTE: don't just take the first
  // non-base canvas found — a stale/orphaned deck.gl canvas (default
  // 300x150, same id="deckgl-overlay", never resized) can be left behind
  // in the DOM alongside the live one, most likely from React StrictMode
  // double-invoking DeckGLOverlay's setup in dev. The live deck.gl
  // overlay canvas is always resized to match the base map canvas
  // exactly, so filter on that instead of DOM order/identity alone.
  const allCanvases = Array.from(containerEl.querySelectorAll("canvas"));
  const deckCandidates = allCanvases.filter(
    (c) => c !== baseCanvas && c.width === baseCanvas.width && c.height === baseCanvas.height
  );
  if (allCanvases.length > 2 || deckCandidates.length > 1) {
    console.warn(
      "[mapExport] unexpected canvas count — possible orphaned deck.gl canvas leak",
      { total: allCanvases.length, matchingCandidates: deckCandidates.length }
    );
  }
  // Prefer the last matching candidate (most recently created) as a
  // tiebreaker if more than one still matches.
  const deckCanvas = deckCandidates[deckCandidates.length - 1] ?? null;

  const targetW = Math.round(baseCanvas.width * scale);
  const targetH = Math.round(baseCanvas.height * scale);

  const out = document.createElement("canvas");
  out.width = targetW;
  out.height = targetH;
  const ctx = out.getContext("2d");
  if (!ctx) throw new Error("Could not create 2D export context");

  // JPEG has no alpha channel — flatten onto white first (matches the
  // app's light basemap) rather than letting transparent regions render
  // as black in most external viewers.
  if (format === "jpeg") {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, targetW, targetH);
  }

  ctx.drawImage(baseCanvas, 0, 0, targetW, targetH);
  if (deckCanvas) {
    ctx.drawImage(deckCanvas, 0, 0, targetW, targetH);
  }

  const mimeType = format === "png" ? "image/png" : "image/jpeg";
  const quality = format === "jpeg" ? jpegQuality : undefined;

  return new Promise<Blob>((resolve, reject) => {
    out.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Canvas export encoding failed"))),
      mimeType,
      quality
    );
  });
}