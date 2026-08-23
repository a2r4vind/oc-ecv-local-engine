import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map, useControl, type MapRef } from "react-map-gl/maplibre";
import { setWorkerUrl } from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { BitmapLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { recolorBitmap, getColor, decodeRawBitmapValues, lookupBitmapValue, type ColormapName, } from "../../utils/colormaps";
import type { RasterResult } from "../../services/backendApi";
import { BboxDrawTool, type LatLonBbox } from "./BboxDrawTool";
import { MapToolbar, type MapTool, type PanDirection } from "./MapToolbar";
import { addOrUpdateGraticule, removeGraticule } from "./Graticule";
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
  // Current panel's bounding box (Option A: whichever sidebar panel is
  // active owns this value in App.tsx's bboxByMode). null if not yet set.
  bbox: MapBbox | null;
  // Phase C: fires when the user draws/edits the rectangle directly on
  // the map (terra-draw), so App.tsx can write it into the active panel's
  // bboxByMode slot and keep the numeric fields in sync.
  onBboxChange: (bbox: MapBbox | null) => void;
  // Ingested file's own spatial extent (from IngestionResult.metadata),
  // used to auto-fit the map view once a file loads.
  spatialBounds: SpatialBounds | null;
  // Day 23: fetched pixel-level data from /raster, rendered as a
  // BitmapLayer (flat-grid) or ScatterplotLayer (swath).
  rasterResult: RasterResult | null;
  colormap: ColormapName;
  opacity: number;
  // Day 30: current query's variable name, shown in map hover tooltips.
  variable: string;
}

// Bridges deck.gl into the MapLibre map instance. Overlaid mode
// (interleaved: false) — see Day 22 for why interleaved mode was rejected
// (maplibre-gl v6 / deck.gl v9.3.7 version-skew).
function DeckGLOverlay({ layers, getTooltip, }: { layers: Layer[]; getTooltip: (info: PickingInfo) => {html: string} | null;}) {
  const overlay = useControl<MapboxOverlay>(
    () => new MapboxOverlay({ interleaved: false, layers, getTooltip })
  );
  overlay.setProps({ layers, getTooltip });
  return null;
}

function toLatLonBbox(bbox: MapBbox): LatLonBbox {
  return { minLat: bbox.latMin, maxLat: bbox.latMax, minLon: bbox.lonMin, maxLon: bbox.lonMax };
}

function toMapBbox(bbox: LatLonBbox): MapBbox {
  return { latMin: bbox.minLat, latMax: bbox.maxLat, lonMin: bbox.minLon, lonMax: bbox.maxLon };
}

function bboxRoughlyEqual(a: LatLonBbox | null, b: LatLonBbox | null): boolean {
  if (a === null || b === null) return a === b;
  const EPS = 1e-6;
  return (
    Math.abs(a.minLat - b.minLat) < EPS &&
    Math.abs(a.maxLat - b.maxLat) < EPS &&
    Math.abs(a.minLon - b.minLon) < EPS &&
    Math.abs(a.maxLon - b.maxLon) < EPS
  );
}

export default function MapView({
  bbox,
  onBboxChange,
  spatialBounds,
  rasterResult,
  colormap,
  opacity,
  variable,
}: MapViewProps) {
  const mapRef = useRef<MapRef | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const lastFittedRef = useRef<SpatialBounds | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Phase C state
  const [activeTool, setActiveTool] = useState<MapTool>("pan");
  const [graticuleOn, setGraticuleOn] = useState(false);
  const drawToolRef = useRef<BboxDrawTool | null>(null);
  // Avoids a stale closure over onBboxChange inside the draw-tool's
  // subscription, which is only set up once (on mapLoaded), not on every
  // render — same stale-reference caution as Day 24's spatialBounds fix.
  const onBboxChangeRef = useRef(onBboxChange);
  useEffect(() => {
    onBboxChangeRef.current = onBboxChange;
  }, [onBboxChange]);

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

  useEffect(() => {
    if (!spatialBounds || !mapLoaded) return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        mapRef.current?.resize();
        fitToBounds(spatialBounds);
      });
    });
  }, [spatialBounds, mapLoaded]);

  // Phase C: instantiate BboxDrawTool once, only after mapLoaded (same
  // onLoad-gate discipline as fitBounds/resize above — calling terra-draw's
  // adapter against a not-yet-ready map is an unnecessary risk to take on).
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;
    const maplibreMap = mapRef.current.getMap();
    const tool = new BboxDrawTool(maplibreMap);
    drawToolRef.current = tool;

    const unsubscribe = tool.onBboxChange((b) => {
      onBboxChangeRef.current(b ? toMapBbox(b) : null);
    });

    return () => {
      unsubscribe();
      tool.destroy();
      drawToolRef.current = null;
    };
  }, [mapLoaded]);

  // Phase C: sync an externally-changed bbox (numeric field edit) down
  // into the draw tool. Guarded by bboxRoughlyEqual so a change that
  // originated FROM the map (drawn, then bubbled up through onBboxChange,
  // then passed back down as the same `bbox` prop) doesn't re-trigger
  // setRectangle() redundantly.
  useEffect(() => {
    const tool = drawToolRef.current;
    if (!tool || !mapLoaded) return;
    const next = bbox ? toLatLonBbox(bbox) : null;
    const current = tool.getRectangle();
    if (bboxRoughlyEqual(current, next)) return;
    if (next) {
      tool.setRectangle(next);
    } else {
      tool.clear();
    }
  }, [bbox, mapLoaded]);

  // Phase C: exclusive draw/pan tool state machine — toggles MapLibre's
  // own dragPan alongside the draw tool's mode, per AKV's spec (drawing
  // and panning must never both be active at once).
  useEffect(() => {
    const tool = drawToolRef.current;
    const maplibreMap = mapRef.current?.getMap();
    if (!tool || !maplibreMap || !mapLoaded) return;

    if (activeTool === "draw") {
      // Disabling dragPan alone wasn't enough in practice — a trackpad's
      // click-and-hold-drag gesture can be picked up by touchZoomRotate
      // (or other handlers) instead of/in addition to dragPan depending
      // on how the OS/browser reports the gesture, letting the map move
      // underneath terra-draw mid-draw and producing a degenerate
      // near-zero rectangle. Disabling every camera-movement handler
      // during draw mode closes that gap entirely. Zoom/pan-arrow
      // toolbar buttons are unaffected — they call map.zoomIn()/panBy()
      // directly, not through these handlers.
      maplibreMap.dragPan.disable();
      maplibreMap.scrollZoom.disable();
      maplibreMap.boxZoom.disable();
      maplibreMap.dragRotate.disable();
      maplibreMap.doubleClickZoom.disable();
      maplibreMap.touchZoomRotate.disable();
      maplibreMap.touchPitch.disable();
      maplibreMap.keyboard.disable();
      maplibreMap.getCanvas().style.cursor = "crosshair";
      tool.startDraw();
    } else {
      maplibreMap.dragPan.enable();
      maplibreMap.scrollZoom.enable();
      maplibreMap.boxZoom.enable();
      maplibreMap.dragRotate.enable();
      maplibreMap.doubleClickZoom.enable();
      maplibreMap.touchZoomRotate.enable();
      maplibreMap.touchPitch.enable();
      maplibreMap.keyboard.enable();
      maplibreMap.getCanvas().style.cursor = "";
      tool.stopDraw();
    }
  }, [activeTool, mapLoaded]);

  // Phase C: graticule add/update/remove, recomputed on pan/zoom
  // (moveend) while enabled.
  useEffect(() => {
    const maplibreMap = mapRef.current?.getMap();
    if (!maplibreMap || !mapLoaded) return;

    if (!graticuleOn) {
      removeGraticule(maplibreMap);
      return;
    }

    const update = () => {
      const b = maplibreMap.getBounds();
      addOrUpdateGraticule(maplibreMap, {
        north: b.getNorth(),
        south: b.getSouth(),
        east: b.getEast(),
        west: b.getWest(),
      });
    };
    update();
    maplibreMap.on("moveend", update);
    return () => {
      maplibreMap.off("moveend", update);
      removeGraticule(maplibreMap);
    };
  }, [graticuleOn, mapLoaded]);

  function handleZoomIn() {
    mapRef.current?.getMap().zoomIn({ duration: 200 });
  }

  function handleZoomOut() {
    mapRef.current?.getMap().zoomOut({ duration: 200 });
  }

  function handlePan(direction: PanDirection) {
    const maplibreMap = mapRef.current?.getMap();
    if (!maplibreMap) return;
    const step = 80; // px
    const offsets: Record<PanDirection, [number, number]> = {
      up: [0, -step],
      down: [0, step],
      left: [-step, 0],
      right: [step, 0],
    };
    maplibreMap.panBy(offsets[direction], { duration: 250 });
  }

  const recoloredCanvas = useMemo(() => {
    if (!rasterResult || rasterResult.type !== "bitmap") return null;
    return recolorBitmap(rasterResult.imageBitmap, colormap);
  }, [rasterResult, colormap]);
  
  // Day 30: decoded raw (denormalized) values, separate from the
  // recolored display canvas above. Colormap-independent — only
  // recomputed when the underlying raster data itself changes, so
  // switching colormaps doesn't trigger a redundant decode.
  const rawBitmapData = useMemo(() => {
    if (!rasterResult || rasterResult.type !== "bitmap") return null;
    return decodeRawBitmapValues(rasterResult.imageBitmap, rasterResult.valueMin, rasterResult.valueMax);
  }, [rasterResult]);

  const pointRenderData = useMemo(() => {
    if (!rasterResult || rasterResult.type !== "points") return null;
    const { lon, lat, value, valueMin, valueMax, pointCount } = rasterResult;

    const positions = new Float32Array(pointCount * 2);
    const colors = new Uint8Array(pointCount * 4);
    // Day 30: denormalized raw values, kept alongside positions/colors so
    // getTooltip can look up an exact value by picked index without a
    // second pass over rasterResult.
    const rawValues = new Float32Array(pointCount);
    for (let i = 0; i < pointCount; i++) {
      positions[i * 2] = lon[i];
      positions[i * 2 + 1] = lat[i];
      const [r, g, b] = getColor(colormap, value[i]);
      colors[i * 4] = r;
      colors[i * 4 + 1] = g;
      colors[i * 4 + 2] = b;
      colors[i * 4 + 3] = 220;
      rawValues[i] = valueMin + value[i] * (valueMax - valueMin);
    }
    return { positions, colors, rawValues, pointCount };
  }, [rasterResult, colormap]);
  
  // Day 30: deck.gl hover tooltip, handling the two structurally
  // different layer types separately.
  //  - "raster-points" (swath, ScatterplotLayer): built from binary
  //    attribute buffers, not a JS object array, so picking returns
  //    info.index (not info.object) — looked up directly against
  //    pointRenderData's parallel arrays.
  //  - "raster-bitmap" (flat-grid, BitmapLayer): picking gives a
  //    geographic info.coordinate, not a data value (the GPU only has
  //    the recolored image) — resolved via lookupBitmapValue() against
  //    the raw decoded value grid + the raster's own geographic bounds.
  const getTooltip = useCallback(
    (info: PickingInfo): { html: string } | null => {
      if (!info.layer) return null;

      if (
        info.layer.id === "raster-points" &&
        info.index !== undefined &&
        info.index >= 0 &&
        pointRenderData
      ) {
        const i = info.index;
        const lon = pointRenderData.positions[i * 2];
        const lat = pointRenderData.positions[i * 2 + 1];
        const raw = pointRenderData.rawValues[i];
        return {
          html: `<b>${variable}</b><br/>${raw.toFixed(4)}<br/><span style="opacity:0.7">${lat.toFixed(4)}°, ${lon.toFixed(4)}°</span>`,
        };
      }

      if (
        info.layer.id === "raster-bitmap" &&
        info.coordinate &&
        rawBitmapData &&
        rasterResult?.type === "bitmap"
      ) {
        const value = lookupBitmapValue(
          info.coordinate as [number, number],
          rasterResult.bounds,
          rawBitmapData
        );
        if (value === null) return null;
        return { html: `<b>${variable}</b><br/>${value.toFixed(4)}` };
      }

      return null;
    },
    [pointRenderData, rawBitmapData, rasterResult, variable]
  );

  const layers: Layer[] = [];

  if (recoloredCanvas && rasterResult?.type === "bitmap") {
    layers.push(
      new BitmapLayer({
        id: "raster-bitmap",
        image: recoloredCanvas,
        bounds: rasterResult.bounds,
        opacity,
        pickable: true, // Day 30: required for getTooltip hover picking
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
        pickable: true, // Day 30: required for getTooltip hover picking
      })
    );
  }

  // NOTE: the bbox rectangle is no longer drawn here via deck.gl
  // PolygonLayer (Day 22-24 behavior) — terra-draw (BboxDrawTool) now owns
  // that rendering directly on the MapLibre map, since it's the
  // interactive/editable one as of Phase C. Rendering both would show two
  // overlapping rectangles.

  return (
    <div className="map-view" ref={containerRef}>
      <Map
        ref={mapRef}
        initialViewState={{ longitude: 72, latitude: 18, zoom: 3 }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={BASE_STYLE}
        onLoad={() => setMapLoaded(true)}
      >
        <DeckGLOverlay layers={layers} getTooltip={getTooltip} />
      </Map>
      <div className="map-view-toolbar-overlay">
        <MapToolbar
          activeTool={activeTool}
          onToolChange={setActiveTool}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onPan={handlePan}
          graticuleOn={graticuleOn}
          onToggleGraticule={() => setGraticuleOn((v) => !v)}
        />
      </div>
    </div>
  );
}