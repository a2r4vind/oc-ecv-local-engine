import { useEffect, useMemo, useRef, useState } from "react";
import { Map, useControl, type MapRef } from "react-map-gl/maplibre";
import { setWorkerUrl } from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { PolygonLayer, BitmapLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { Layer } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { recolorBitmap, getColor, type ColormapName } from "../../utils/colormaps";
import type { RasterResult } from "../../services/backendApi";
import "./MapView.css";

// MapLibre GL v6 ships ESM-only and requires the worker URL to be wired
// explicitly under Vite — otherwise the worker 404s, map.transform never
// initializes, and both MapLibre's render loop and deck.gl's per-frame
// viewport sync (getViewport) throw "map.transform.height is undefined".
setWorkerUrl(maplibreWorkerUrl);

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
  // Day 23: fetched pixel-level data from /raster, rendered as a
  // BitmapLayer (flat-grid) or ScatterplotLayer (swath) beneath the bbox
  // rectangle. null until "Run Query" is submitted.
  rasterResult: RasterResult | null;
  // Active colormap — applied client-side against rasterResult, never
  // requires a backend re-fetch when changed.
  colormap: ColormapName;
  // Day 24: layer opacity (0-1), applied on top of each pixel/point's
  // own validity-derived alpha — masked/invalid data stays invisible
  // regardless of this value; it only affects how strongly VALID data
  // shows through the base map underneath.
  opacity: number;
}

// Bridges deck.gl into the MapLibre map instance. Uses overlaid mode
// (interleaved: false) — deck.gl renders into its own separate canvas
// rather than sharing MapLibre's internal WebGL2 context/transform every
// frame. Chosen on Day 22 after interleaved mode produced repeated
// "map.transform.height" errors against this maplibre-gl v6 / deck.gl
// v9.3.7 pairing — overlaid mode doesn't read MapLibre's internals
// per-frame, so it's far less exposed to that version-skew.
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

export default function MapView({ bbox, spatialBounds, rasterResult, colormap, opacity }: MapViewProps) {
  const mapRef = useRef<MapRef | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  // Tracks which spatialBounds object we've successfully fit the view
  // to, so repeated resize events don't keep forcing the view back to
  // the file's full extent — only a genuinely new file (new
  // spatialBounds reference) should trigger a re-fit.
  const lastFittedRef = useRef<SpatialBounds | null>(null);
  // Root cause (corrected from the earlier font-loading theory, which
  // wasn't the actual issue): react-map-gl's Map fires onLoad once
  // MapLibre's internal style/tile/GL context is genuinely ready.
  // Calling fitBounds()/resize() before that is a known source of
  // silent, intermittent no-ops — this is why it "sometimes" worked
  // (whenever onLoad happened to have already fired by the time our
  // effect ran) and why it always looked correct after Run Query (by
  // then, plenty of time/reflows had passed for onLoad to have long
  // since fired). Gating on this actual readiness signal, instead of
  // guessing at generic resize/font timing, targets the real race.
  const [mapLoaded, setMapLoaded] = useState(false);

  function fitToBounds(bounds: SpatialBounds) {
    if (!mapRef.current) return;
    const [latMin, latMax] = bounds.latRange;
    const [lonMin, lonMax] = bounds.lonRange;
    if (![latMin, latMax, lonMin, lonMax].every(Number.isFinite)) return;

    mapRef.current.fitBounds(
      [
        [lonMin, latMin],
        [lonMax, latMax],
      ],
      { padding: 40, duration: 600 }
    );
    lastFittedRef.current = bounds;
  }

  // Ongoing safety net for layout shifts after the map has loaded
  // (sidebar content height changes, window resize) — still useful on
  // top of the onLoad gate below, since container size can still change
  // after initial load.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !mapLoaded) return;
    const observer = new ResizeObserver(() => {
      mapRef.current?.resize();
      if (spatialBounds && lastFittedRef.current !== spatialBounds) {
        fitToBounds(spatialBounds);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [spatialBounds, mapLoaded]);

  // Auto-zoom to the ingested file's spatial extent — gated on
  // mapLoaded so this never fires before MapLibre's GL context/style
  // are actually ready. requestAnimationFrame (double-wrapped) waits
  // for the browser to have painted at least one frame post-load,
  // giving the container's final flex-determined size time to be
  // reflected before we ask MapLibre to resize/fit against it.
  useEffect(() => {
    if (!spatialBounds || !mapLoaded) return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        mapRef.current?.resize();
        fitToBounds(spatialBounds);
      });
    });
  }, [spatialBounds, mapLoaded]);

  // Recolor the fetched grayscale+alpha bitmap against the active
  // colormap. Memoized on [rasterResult, colormap] specifically — without
  // this, every bbox keystroke (which re-renders MapView via App's
  // mapBbox state) would re-run canvas recoloring even though neither
  // the raster data nor the colormap actually changed.
  const recoloredCanvas = useMemo(() => {
    if (!rasterResult || rasterResult.type !== "bitmap") return null;
    return recolorBitmap(rasterResult.imageBitmap, colormap);
  }, [rasterResult, colormap]);

  // Same memoization reasoning for swath point colors — recomputing a
  // per-point color lookup across potentially hundreds of thousands of
  // points on every keystroke would be wasteful.
  const pointRenderData = useMemo(() => {
    if (!rasterResult || rasterResult.type !== "points") return null;
    const { lon, lat, value, pointCount } = rasterResult;

    const positions = new Float32Array(pointCount * 2);
    const colors = new Uint8Array(pointCount * 4);
    for (let i = 0; i < pointCount; i++) {
      positions[i * 2] = lon[i];
      positions[i * 2 + 1] = lat[i];
      const [r, g, b] = getColor(colormap, value[i]);
      colors[i * 4] = r;
      colors[i * 4 + 1] = g;
      colors[i * 4 + 2] = b;
      colors[i * 4 + 3] = 220;
    }
    return { positions, colors, pointCount };
  }, [rasterResult, colormap]);

  const layers: Layer[] = [];

  // Raster data layer first, so the bbox rectangle (added below) draws
  // on top of it rather than being hidden underneath.
  if (recoloredCanvas && rasterResult?.type === "bitmap") {
    layers.push(
      new BitmapLayer({
        id: "raster-bitmap",
        image: recoloredCanvas,
        bounds: rasterResult.bounds,
        opacity,
      })
    );
  }

  if (pointRenderData) {
    layers.push(
      new ScatterplotLayer({
        id: "raster-points",
        data: {
          length: pointRenderData.pointCount,
          attributes: {
            getPosition: { value: pointRenderData.positions, size: 2 },
            getFillColor: { value: pointRenderData.colors, size: 4 },
          },
        },
        radiusMinPixels: 1.5,
        radiusMaxPixels: 4,
        stroked: false,
        opacity,
      })
    );
  }

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
    <div className="map-view" ref={containerRef}>
      <Map
        ref={mapRef}
        initialViewState={{ longitude: 72, latitude: 18, zoom: 3 }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={BASE_STYLE}
        onLoad={() => setMapLoaded(true)}
      >
        <DeckGLOverlay layers={layers} />
      </Map>
    </div>
  );
}