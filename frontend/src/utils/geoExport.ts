import { fetchGeoExport, type StatsQuery } from "../services/backendApi";
import { saveBinaryFile, blobToUint8Array } from "./saveFile";

/**
 * Day 38: fetches georeferenced raster/swath data from /export-geo and
 * prompts Tauri's native save dialog — the GIS-interoperable counterpart
 * to dataExport.ts's analysis-oriented CSV/.bin export. Format is NOT a
 * caller choice (unlike raw export's csv/bin): the backend picks
 * GeoTIFF (flat-grid) or CF-1.8 NetCDF (swath) based on file structure,
 * and reports which one via the X-Export-Kind header, so the saved
 * file's extension always matches its actual contents.
 */
export async function exportGeoData(query: StatsQuery): Promise<string | null> {
  const { blob, exportKind } = await fetchGeoExport(query);
  const bytes = await blobToUint8Array(blob);
  const extension = exportKind === "geotiff" ? "tif" : "nc";
  return saveBinaryFile(bytes, {
    defaultFileName: `oc-ecv-export.${extension}`,
    filterName: exportKind === "geotiff" ? "GeoTIFF" : "NetCDF (CF swath)",
    extensions: [extension],
  });
}