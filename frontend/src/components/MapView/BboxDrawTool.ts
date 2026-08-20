// frontend/src/components/MapView/BboxDrawTool.ts

import type { Map as MaplibreMap } from "maplibre-gl";
import {
  TerraDraw,
  TerraDrawRectangleMode,
  TerraDrawSelectMode,
  type GeoJSONStoreFeatures,
} from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";

export interface LatLonBbox {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

type TDFeatureId = string | number;
type BboxChangeListener = (bbox: LatLonBbox | null) => void;

const RECTANGLE_MODE_NAME = "rectangle";
const PAN_MODE_NAME = "select";

export class BboxDrawTool {
  private draw: TerraDraw;
  private map: MaplibreMap;
  private listeners: Set<BboxChangeListener> = new Set();
  private currentMode: "rectangle" | "pan" = "pan";
  private isProgrammaticUpdate = false;

  constructor(map: MaplibreMap) {
    this.map = map;
    this.draw = new TerraDraw({
      adapter: new TerraDrawMapLibreGLAdapter({ map }),
      modes: [
        new TerraDrawRectangleMode({
          drawInteraction: "click-move-or-drag",
          styles: {
            fillColor: "#2563eb",
            fillOpacity: 0.15,
            outlineColor: "#2563eb",
            outlineWidth: 2,
          },
        }),
        new TerraDrawSelectMode({
          flags: {
            rectangle: {
              feature: {
                draggable: false,
                coordinates: {
                  midpoints: false,
                  draggable: false,
                  deletable: false,
                },
              },
            },
          },
        }),
      ],
    });

    this.draw.start();
    this.draw.setMode(PAN_MODE_NAME);

    // Only clean up stale RECTANGLE features, not everything in the
    // store — TerraDrawSelectMode's edit flags are all off so it
    // shouldn't be creating extra features, but scoping this cleanup by
    // mode keeps the blast radius correct regardless.
    this.draw.on("finish", (id) => {
      const snapshot = this.draw.getSnapshot();
      const staleIds = snapshot
        .filter((f) => f.id !== id && f.properties?.mode === RECTANGLE_MODE_NAME)
        .map((f) => f.id)
        .filter((fid): fid is TDFeatureId => fid !== undefined);

      if (staleIds.length > 0) {
        this.runProgrammatic(() => {
          this.draw.removeFeatures(staleIds);
        });
      }
      this.emitFromFeatureId(id);
      this.forceRepaint();
    });

    this.draw.on("change", (ids, type) => {
      this.forceRepaint();
      if (this.isProgrammaticUpdate) return;
      if (type === "delete") {
        this.emit(null);
        return;
      }
      if (ids.length > 0) {
        this.emitFromFeatureId(ids[ids.length - 1]);
      }
    });
  }

  startDraw(): void {
    this.currentMode = "rectangle";
    this.draw.setMode(RECTANGLE_MODE_NAME);
    this.attachLiveRepaintListener();
  }

  stopDraw(): void {
    this.currentMode = "pan";
    this.draw.setMode(PAN_MODE_NAME);
    this.detachLiveRepaintListener();
  }

  getActiveMode(): "rectangle" | "pan" {
    return this.currentMode;
  }

  clear(): void {
    this.runProgrammatic(() => {
      const snapshot = this.draw.getSnapshot();
      const ids = snapshot
        .map((f) => f.id)
        .filter((id): id is TDFeatureId => id !== undefined);
      if (ids.length > 0) {
        this.draw.removeFeatures(ids);
      }
    });
  }

  /**
   * No-ops if the incoming bbox already matches what's on the map —
   * critical guard preventing MapView's sync effect (which fires after
   * every user-drawn rectangle, since the finished bbox round-trips up
   * through App.tsx and back down as a prop) from unconditionally
   * deleting + re-adding a feature via the raw store API when nothing
   * actually changed. That unconditional remove+re-add was previously
   * corrupting TerraDrawRectangleMode's internal state after the first
   * draw in a session.
   */
  setRectangle(bbox: LatLonBbox): void {
    const current = this.getRectangle();
    if (current && this.bboxEqual(current, bbox)) return;

    this.runProgrammatic(() => {
      const snapshot = this.draw.getSnapshot();
      const staleIds = snapshot
        .map((f) => f.id)
        .filter((id): id is TDFeatureId => id !== undefined);
      if (staleIds.length > 0) {
        this.draw.removeFeatures(staleIds);
      }

      const { minLat, maxLat, minLon, maxLon } = bbox;
      const feature: GeoJSONStoreFeatures = {
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat],
            ],
          ],
        },
        properties: {
          mode: RECTANGLE_MODE_NAME,
        },
      } as GeoJSONStoreFeatures;

      this.draw.addFeatures([feature]);
    });
  }

  getRectangle(): LatLonBbox | null {
    const snapshot = this.draw.getSnapshot();
    const feature = snapshot.find((f) => f.properties?.mode === RECTANGLE_MODE_NAME);
    if (!feature || feature.geometry.type !== "Polygon") return null;
    const ring = feature.geometry.coordinates[0] as number[][];
    return this.boundsFromRing(ring);
  }

  onBboxChange(listener: BboxChangeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  destroy(): void {
    this.detachLiveRepaintListener();
    this.listeners.clear();
    this.draw.stop();
  }

  // Live in-progress preview (rectangle following the cursor between the
  // first and second click, or during a press-drag) is suspected to use
  // an internal terra-draw render path that doesn't go through the
  // public "change"/"finish" events forceRepaint() is otherwise wired
  // to. Blunt, event-system-agnostic backstop: force a repaint on every
  // raw pointer movement while draw mode is active. Only attached during
  // active drawing, not pan mode.
  private repaintOnMove = () => this.forceRepaint();

  private attachLiveRepaintListener(): void {
    const canvas = this.map.getCanvas();
    canvas.addEventListener("mousemove", this.repaintOnMove);
    canvas.addEventListener("touchmove", this.repaintOnMove);
    canvas.addEventListener("pointermove", this.repaintOnMove);
  }

  private detachLiveRepaintListener(): void {
    const canvas = this.map.getCanvas();
    canvas.removeEventListener("mousemove", this.repaintOnMove);
    canvas.removeEventListener("touchmove", this.repaintOnMove);
    canvas.removeEventListener("pointermove", this.repaintOnMove);
  }

  private forceRepaint(): void {
    requestAnimationFrame(() => {
      if (this.map && typeof this.map.triggerRepaint === "function") {
        this.map.triggerRepaint();
      }
    });
  }

  private runProgrammatic(fn: () => void): void {
    this.isProgrammaticUpdate = true;
    try {
      fn();
    } finally {
      this.isProgrammaticUpdate = false;
    }
  }

  private emitFromFeatureId(id: TDFeatureId): void {
    const snapshot = this.draw.getSnapshot();
    const feature = snapshot.find((f) => f.id === id);
    if (!feature || feature.geometry.type !== "Polygon") {
      this.emit(null);
      return;
    }
    const ring = feature.geometry.coordinates[0] as number[][];
    // Defensive guard: a genuinely-finished rectangle always has 5
    // coordinate pairs (4 corners + closing point repeating the first).
    // Emitting from a malformed/in-progress ring (fewer points, or a
    // degenerate single-point ring) is a likely source of the
    // "erratic/inverted values" symptom — skip rather than emit garbage.
    if (!ring || ring.length < 5) {
      return;
    }
    const bbox = this.boundsFromRing(ring);
    this.emit(bbox);
  }

  private bboxEqual(a: LatLonBbox, b: LatLonBbox): boolean {
    const EPS = 1e-9;
    return (
      Math.abs(a.minLat - b.minLat) < EPS &&
      Math.abs(a.maxLat - b.maxLat) < EPS &&
      Math.abs(a.minLon - b.minLon) < EPS &&
      Math.abs(a.maxLon - b.maxLon) < EPS
    );
  }

  private boundsFromRing(ring: number[][]): LatLonBbox {
    const lons = ring.map((c) => c[0]);
    const lats = ring.map((c) => c[1]);
    return {
      minLat: Math.min(...lats),
      maxLat: Math.max(...lats),
      minLon: Math.min(...lons),
      maxLon: Math.max(...lons),
    };
  }

  private emit(bbox: LatLonBbox | null): void {
    this.listeners.forEach((fn) => fn(bbox));
  }
}