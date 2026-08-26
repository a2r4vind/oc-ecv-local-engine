import { fetchRawExport, type RawExportFormat, type StatsQuery } from "../services/backendApi";
import { saveBinaryFile, blobToUint8Array } from "./saveFile";

/**
 * Day 37: fetches raw (unrendered) pixel data from /export-raw and
 * prompts Tauri's native save dialog — the numeric-data counterpart to
 * mapExport.ts's PNG/JPEG visual export. Takes the exact same
 * StatsQuery object App.tsx already builds for /stats and /raster
 * (captured as `lastQuery` at query-submit time), so raw export always
 * matches what's actually on screen, not the form's current
 * (possibly since-edited, not-yet-run) field values.
 */
export async function exportRawData(
  query: StatsQuery,
  format: RawExportFormat
): Promise<string | null> {
  const blob = await fetchRawExport(query, format);
  const bytes = await blobToUint8Array(blob);
  const extension = format === "csv" ? "csv" : "bin";

  return saveBinaryFile(bytes, {
    defaultFileName: `oc-ecv-export.${extension}`,
    filterName: format === "csv" ? "CSV Table" : "Binary Data",
    extensions: [extension],
  });
}