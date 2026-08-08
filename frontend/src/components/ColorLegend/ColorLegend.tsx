import { getGradientCss, type ColormapName } from "../../utils/colormaps";
import "./ColorLegend.css";

interface ColorLegendProps {
  colormap: ColormapName;
  valueMin: number;
  valueMax: number;
  variable?: string;
}

export default function ColorLegend({ colormap, valueMin, valueMax, variable }: ColorLegendProps) {
  return (
    <div className="color-legend">
      {variable && <div className="color-legend-title">{variable}</div>}
      <div className="color-legend-bar" style={{ background: getGradientCss(colormap) }} />
      <div className="color-legend-labels">
        <span>{valueMin.toFixed(3)}</span>
        <span>{valueMax.toFixed(3)}</span>
      </div>
    </div>
  );
}