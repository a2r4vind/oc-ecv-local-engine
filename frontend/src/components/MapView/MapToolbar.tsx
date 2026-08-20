// frontend/src/components/MapView/MapToolbar.tsx
//
// Presentational toolbar only — owns no state of its own. activeTool state
// lives in MapView.tsx (single source of truth, wired to both this toolbar's
// highlight and BboxDrawTool's actual mode + MapLibre's dragPan setting), so
// this component can never drift out of sync with what the map is actually
// doing.

import "./MapToolbar.css";

export type MapTool = "draw" | "pan";
export type PanDirection = "up" | "down" | "left" | "right";

interface MapToolbarProps {
  activeTool: MapTool;
  onToolChange: (tool: MapTool) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onPan: (direction: PanDirection) => void;
  graticuleOn: boolean;
  onToggleGraticule: () => void;
}

export function MapToolbar({
  activeTool,
  onToolChange,
  onZoomIn,
  onZoomOut,
  onPan,
  graticuleOn,
  onToggleGraticule,
}: MapToolbarProps) {
  return (
    <div className="map-toolbar" role="toolbar" aria-label="Map controls">
      <div className="map-toolbar-group">
        <button
          type="button"
          className={`map-toolbar-btn ${activeTool === "draw" ? "active" : ""}`}
          aria-pressed={activeTool === "draw"}
          title="Draw bounding box"
          onClick={() => onToolChange("draw")}
        >
          <DrawIcon />
        </button>
        <button
          type="button"
          className={`map-toolbar-btn ${activeTool === "pan" ? "active" : ""}`}
          aria-pressed={activeTool === "pan"}
          title="Pan"
          onClick={() => onToolChange("pan")}
        >
          <PanIcon />
        </button>
      </div>

      <div className="map-toolbar-group">
        <button type="button" className="map-toolbar-btn" title="Zoom in" onClick={onZoomIn}>
          <ZoomInIcon />
        </button>
        <button type="button" className="map-toolbar-btn" title="Zoom out" onClick={onZoomOut}>
          <ZoomOutIcon />
        </button>
      </div>

      <div className="map-toolbar-group map-toolbar-pan-pad">
        <button
          type="button"
          className="map-toolbar-btn map-toolbar-pan-up"
          title="Pan up"
          onClick={() => onPan("up")}
        >
          <ArrowIcon direction="up" />
        </button>
        <button
          type="button"
          className="map-toolbar-btn map-toolbar-pan-left"
          title="Pan left"
          onClick={() => onPan("left")}
        >
          <ArrowIcon direction="left" />
        </button>
        <button
          type="button"
          className="map-toolbar-btn map-toolbar-pan-right"
          title="Pan right"
          onClick={() => onPan("right")}
        >
          <ArrowIcon direction="right" />
        </button>
        <button
          type="button"
          className="map-toolbar-btn map-toolbar-pan-down"
          title="Pan down"
          onClick={() => onPan("down")}
        >
          <ArrowIcon direction="down" />
        </button>
      </div>

      <div className="map-toolbar-group">
        <button
          type="button"
          className={`map-toolbar-btn ${graticuleOn ? "active" : ""}`}
          aria-pressed={graticuleOn}
          title="Toggle lat/lon grid"
          onClick={onToggleGraticule}
        >
          <GridIcon />
        </button>
      </div>
    </div>
  );
}

// --- Inline SVG icons (stroke=currentColor, no emoji — WebKitGTK tofu-box precedent) ---

function DrawIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="6" width="16" height="12" rx="1" strokeDasharray="3 3" />
    </svg>
  );
}

function PanIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 11V6a1.5 1.5 0 0 1 3 0v5" />
      <path d="M12 11V4.5a1.5 1.5 0 0 1 3 0V11" />
      <path d="M15 11V6a1.5 1.5 0 0 1 3 0v7" />
      <path d="M6 12.5V10a1.5 1.5 0 0 1 3 0v2.5" />
      <path d="M6 12.5c-1 0-2 .5-2 2 0 3 2.5 6.5 6 6.5h4c3 0 5-2 5-5v-4" />
    </svg>
  );
}

function ZoomInIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" />
      <path d="M11 8v6M8 11h6" />
    </svg>
  );
}

function ZoomOutIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" />
      <path d="M8 11h6" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="1" />
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
    </svg>
  );
}

function ArrowIcon({ direction }: { direction: PanDirection }) {
  const rotation = { up: 0, right: 90, down: 180, left: 270 }[direction];
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ transform: `rotate(${rotation}deg)` }}
    >
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  );
}