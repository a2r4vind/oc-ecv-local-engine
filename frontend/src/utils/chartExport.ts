// Deliberately NOT "plotly.js" here — that pulls in every trace module
// (including "image", which requires the Node Buffer polyfill package
// "buffer/" that isn't installed) into Vite's dependency pre-bundling.
// react-plotly.js's own internal plotly.js import (used for the actual
// interactive charts) is untouched by this and keeps working normally.
import Plotly from "plotly.js-dist-min";

export type ExportFormat = "png" | "jpeg";

interface ExportPlotOptions {
  graphDiv: HTMLElement;
  format: ExportFormat;
  scale?: number; // Plotly's own resolution multiplier, default 3
}

/**
 * Wraps Plotly.toImage. Unlike the map export path, Plotly already
 * handles high-res output natively via its `scale` param — no manual
 * canvas compositing needed here.
 */
export async function exportPlotToBlob({
  graphDiv,
  format,
  scale = 3,
}: ExportPlotOptions): Promise<Blob> {
  const dataUrl = await Plotly.toImage(graphDiv, {
    format,
    width: graphDiv.offsetWidth || 800,
    height: graphDiv.offsetHeight || 480,
    scale,
  });
  const res = await fetch(dataUrl);
  return await res.blob();
}