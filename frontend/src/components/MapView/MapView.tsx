import { useEffect, useRef } from "react";
import { Map, useControl, type MapRef } from "react-map-gl/maplibre";
import { setWorkerUrl } from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { PolygonLayer } from "@deck.gl/layers";
import type { Layer } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "./MapView.css";

// MapLibre GL v6 ships ESM-only and requires the worker URL to be wired
// explicitly under Vite — otherwise the worker 404s, map.transform never
// initializes, and both MapLibre's render loop and deck.gl's per-frame
// viewport sync (getViewport) throw "map.transform.height is undefined".
setWorkerUrl(maplibreWorkerUrl)


// Free, no-API-key vector basemap style (CARTO Positron), same one used in
// deck.gl's own official MapLibre examples.
const BASE_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

export interface MapBbox {
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
}

export interface SpatialBounds {
  latRange: [number, number];
  lonRange: [number, number];
}

interface MapViewProps {
  // Current query bounding box (from ParameterSelector), or null if not
  // yet fully specified — drawn as an overlay rectangle when valid.
  bbox: MapBbox | null;
  // Ingested file's own spatial extent (from IngestionResult.metadata),
  // used to auto-fit the map view once a file loads.
  spatialBounds: SpatialBounds | null;
}

// Bridges deck.gl into the MapLibre map instance via the official
// interleaved-mode pattern (single shared WebGL2 canvas).
function DeckGLOverlay({ layers }: { layers: Layer[] }) {
  const overlay = useControl<MapboxOverlay>(
    () => new MapboxOverlay({ interleaved: false, layers })
  );
  overlay.setProps({ layers });
  return null;
}

function isValidBbox(bbox: MapBbox | null): bbox is MapBbox {
  if (!bbox) return false;
  const { latMin, latMax, lonMin, lonMax } = bbox;
  return (
    [latMin, latMax, lonMin, lonMax].every((v) => Number.isFinite(v)) &&
    latMin < latMax &&
    lonMin < lonMax
  );
}

export default function MapView({ bbox, spatialBounds }: MapViewProps) {
  const mapRef = useRef<MapRef | null>(null);

  // Auto-zoom to the ingested file's spatial extent whenever it changes
  // (new file loaded).
  useEffect(() => {
    if (!spatialBounds || !mapRef.current) return;
    const [latMin, latMax] = spatialBounds.latRange;
    const [lonMin, lonMax] = spatialBounds.lonRange;
    if (![latMin, latMax, lonMin, lonMax].every(Number.isFinite)) return;

    mapRef.current.fitBounds(
      [
        [lonMin, latMin],
        [lonMax, latMax],
      ],
      { padding: 40, duration: 600 }
    );
  }, [spatialBounds]);

  const layers: Layer[] = [];

  if (isValidBbox(bbox)) {
    const { latMin, latMax, lonMin, lonMax } = bbox;
    layers.push(
      new PolygonLayer({
        id: "query-bbox",
        data: [
          {
            polygon: [
              [lonMin, latMin],
              [lonMax, latMin],
              [lonMax, latMax],
              [lonMin, latMax],
              [lonMin, latMin],
            ],
          },
        ],
        getPolygon: (d: { polygon: number[][] }) => d.polygon,
        stroked: true,
        filled: true,
        getFillColor: [0, 128, 255, 40],
        getLineColor: [0, 128, 255, 200],
        lineWidthMinPixels: 2,
      })
    );
  }

  return (
    <div className="map-view">
      <Map
        ref={mapRef}
        initialViewState={{ longitude: 72, latitude: 18, zoom: 3 }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={BASE_STYLE}
      >
        <DeckGLOverlay layers={layers} />
      </Map>
    </div>
  );
}