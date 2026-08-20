// frontend/src/components/MapView/Graticule.ts

import type { Map as MaplibreMap, GeoJSONSource } from "maplibre-gl";

const GRATICULE_SOURCE_ID = "oc-ecv-graticule";
const GRATICULE_LAYER_ID = "oc-ecv-graticule-lines";
const GRATICULE_LABEL_SOURCE_ID = "oc-ecv-graticule-labels";
const GRATICULE_LABEL_LAYER_ID = "oc-ecv-graticule-label-text";

function formatLat(lat: number): string {
  const rounded = Math.round(lat * 1e6) / 1e6;
  if (rounded === 0) return "0°";
  return `${Math.abs(rounded)}°${rounded > 0 ? "N" : "S"}`;
}

function formatLon(lon: number): string {
  const rounded = Math.round(lon * 1e6) / 1e6;
  if (rounded === 0) return "0°";
  return `${Math.abs(rounded)}°${rounded > 0 ? "E" : "W"}`;
}

export interface ViewBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

/** Picks a "nice" grid spacing (1/2/5 * 10^n) yielding ~4-10 lines across
 *  the current view span — avoids a cluttered mesh when zoomed out or an
 *  invisible one-or-two-line grid when zoomed in. */
function niceStep(spanDegrees: number): number {
  const rough = spanDegrees / 6;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
  const residual = rough / magnitude;
  let niceResidual: number;
  if (residual < 1.5) niceResidual = 1;
  else if (residual < 3.5) niceResidual = 2;
  else if (residual < 7.5) niceResidual = 5;
  else niceResidual = 10;
  return niceResidual * magnitude;
}

export function buildGraticuleGeoJSON(bounds: ViewBounds): GeoJSON.FeatureCollection {
  const { north, south, east, west } = bounds;
  const latSpan = Math.max(north - south, 0.0001);
  const lonSpan = Math.max(east - west, 0.0001);
  const step = Math.max(niceStep(latSpan), niceStep(lonSpan));

  const features: GeoJSON.Feature[] = [];

  const startLat = Math.floor(south / step) * step;
  for (let lat = startLat; lat <= north + step; lat += step) {
    if (lat < -90 || lat > 90) continue;
    features.push({
      type: "Feature",
      properties: { kind: "parallel", value: Number(lat.toFixed(6)) },
      geometry: {
        type: "LineString",
        coordinates: [
          [west - lonSpan, lat],
          [east + lonSpan, lat],
        ],
      },
    });
  }

  const startLon = Math.floor(west / step) * step;
  for (let lon = startLon; lon <= east + step; lon += step) {
    features.push({
      type: "Feature",
      properties: { kind: "meridian", value: Number(lon.toFixed(6)) },
      geometry: {
        type: "LineString",
        coordinates: [
          [lon, south - latSpan],
          [lon, north + latSpan],
        ],
      },
    });
  }

  return { type: "FeatureCollection", features };
}

/**
 * Label points for the same grid: latitude labels placed along the left
 * (west) edge, longitude labels along the top (north) edge — matching
 * NASA Giovanni's own graticule label placement. Offset slightly inward
 * from the raw edge so labels aren't clipped by the map container.
 */
export function buildGraticuleLabelsGeoJSON(bounds: ViewBounds): GeoJSON.FeatureCollection {
  const { north, south, east, west } = bounds;
  const latSpan = Math.max(north - south, 0.0001);
  const lonSpan = Math.max(east - west, 0.0001);
  const step = Math.max(niceStep(latSpan), niceStep(lonSpan));
  const latInset = latSpan * 0.04;
  const lonInset = lonSpan * 0.04;

  const features: GeoJSON.Feature[] = [];

  const startLat = Math.floor(south / step) * step;
  for (let lat = startLat; lat <= north + step; lat += step) {
    if (lat < -90 || lat > 90) continue;
    if (lat <= south || lat >= north) continue; // skip labels off-screen
    features.push({
      type: "Feature",
      properties: { label: formatLat(lat) },
      geometry: { type: "Point", coordinates: [west + lonInset, lat] },
    });
  }

  const startLon = Math.floor(west / step) * step;
  for (let lon = startLon; lon <= east + step; lon += step) {
    if (lon <= west || lon >= east) continue;
    features.push({
      type: "Feature",
      properties: { label: formatLon(lon) },
      geometry: { type: "Point", coordinates: [lon, north - latInset] },
    });
  }

  return { type: "FeatureCollection", features };
}

export function addOrUpdateGraticule(map: MaplibreMap, bounds: ViewBounds): void {
  const lineData = buildGraticuleGeoJSON(bounds);
  const labelData = buildGraticuleLabelsGeoJSON(bounds);

  const existingLines = map.getSource(GRATICULE_SOURCE_ID) as GeoJSONSource | undefined;
  if (existingLines) {
    existingLines.setData(lineData as GeoJSON.FeatureCollection);
  } else {
    map.addSource(GRATICULE_SOURCE_ID, { type: "geojson", data: lineData });
    map.addLayer({
      id: GRATICULE_LAYER_ID,
      type: "line",
      source: GRATICULE_SOURCE_ID,
      paint: {
        "line-color": "#64748b",
        "line-width": 0.75,
        "line-opacity": 0.6,
        "line-dasharray": [2, 2],
      },
    });
  }

  const existingLabels = map.getSource(GRATICULE_LABEL_SOURCE_ID) as GeoJSONSource | undefined;
  if (existingLabels) {
    existingLabels.setData(labelData as GeoJSON.FeatureCollection);
  } else {
    map.addSource(GRATICULE_LABEL_SOURCE_ID, { type: "geojson", data: labelData });
    map.addLayer({
      id: GRATICULE_LABEL_LAYER_ID,
      type: "symbol",
      source: GRATICULE_LABEL_SOURCE_ID,
      layout: {
        "text-field": ["get", "label"],
        "text-size": 11,
        "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
        "text-allow-overlap": false,
        "text-anchor": "top-left",
        "text-offset": [0.2, 0.2],
      },
      paint: {
        "text-color": "#334155",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.4,
      },
    });
  }
}

export function removeGraticule(map: MaplibreMap): void {
  if (map.getLayer(GRATICULE_LABEL_LAYER_ID)) map.removeLayer(GRATICULE_LABEL_LAYER_ID);
  if (map.getSource(GRATICULE_LABEL_SOURCE_ID)) map.removeSource(GRATICULE_LABEL_SOURCE_ID);
  if (map.getLayer(GRATICULE_LAYER_ID)) map.removeLayer(GRATICULE_LAYER_ID);
  if (map.getSource(GRATICULE_SOURCE_ID)) map.removeSource(GRATICULE_SOURCE_ID);
}