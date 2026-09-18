import { getGradientCss, getSteppedGradientCss, getStepBoundaries, type ColormapName } from "../../utils/colormaps";
import "./ColorLegend.css";

interface ColorLegendProps {
  colormap: ColormapName;
  valueMin: number;
  valueMax: number;
  variable?: string;
  steps?: number; // mentor item #1: 0 (default) = continuous, >=2 = discrete bands
}

export default function ColorLegend({ colormap, valueMin, valueMax, variable, steps = 0 }: ColorLegendProps) {
  const stepped = steps >= 2;
  const gradient = stepped ? getSteppedGradientCss(colormap, steps) : getGradientCss(colormap);
  const boundaries = stepped ? getStepBoundaries(valueMin, valueMax, steps) : null;

  return (
    <div className="color-legend">
      {variable && <div className="color-legend-title">{variable}</div>}
      <div className="color-legend-bar" style={{ background: gradient }} />
      {boundaries ? (
        <div className="color-legend-ticks">
          {boundaries.map((v, i) => (
            <span key={i}>{v.toFixed(3)}</span>
          ))}
        </div>
      ) : (
        <div className="color-legend-labels">
          <span>{valueMin.toFixed(3)}</span>
          <span>{valueMax.toFixed(3)}</span>
        </div>
      )}
    </div>
  );
}