import Plot from "react-plotly.js";
import type { ScatterResult } from "../../services/backendApi";

interface ScatterChartProps {
  data: ScatterResult;
}

export default function ScatterChart({ data }: ScatterChartProps) {
  const wasSubsampled =
    (data.total_pair_count ?? 0) > (data.returned_pair_count ?? 0);

  return (
    <div className="chart-wrapper">
      <Plot
        data={[
          {
            x: data.x,
            y: data.y,
            // scattergl (WebGL), not scatter (SVG) — point counts here can
            // reach the tens of thousands (67,299 in today's real-data
            // verification). Same WebGL-over-SVG performance reasoning
            // already established for the raster ScatterplotLayer on Day
            // 23; SVG rendering at this point count would visibly lag.
            type: "scattergl",
            mode: "markers",
            marker: { size: 4, color: "#2563eb", opacity: 0.4 },
          },
        ]}
        layout={{
          title: { text: `${data.variable_y} vs ${data.variable_x}` },
          autosize: true,
          height: 480,
          margin: { t: 40, r: 50, b: 80, l: 60 },
          xaxis: { title: { text: data.variable_x } },
          yaxis: { title: { text: data.variable_y } },
        }}
        style={{ width: "100%" }}
        useResizeHandler
        config={{ displaylogo: false, responsive: true }}
      />
      <p style={{ fontSize: "0.8rem", color: "#555", textAlign: "center" }}>
        {data.returned_pair_count?.toLocaleString()} pixel pairs
        {wasSubsampled &&
          ` (subsampled from ${data.total_pair_count?.toLocaleString()})`}
        {" · "}
        Correlation:{" "}
        {data.correlation !== null && data.correlation !== undefined
          ? data.correlation.toFixed(4)
          : "n/a"}
      </p>
    </div>
  );
}