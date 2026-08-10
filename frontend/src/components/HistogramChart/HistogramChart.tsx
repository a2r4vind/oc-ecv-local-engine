import Plot from "react-plotly.js";
import type { HistogramResult } from "../../services/backendApi";

interface HistogramChartProps {
  data: HistogramResult;
  variable: string;
}

export default function HistogramChart({ data, variable }: HistogramChartProps) {
  const edges = data.bin_edges ?? [];
  const counts = data.counts ?? [];
  // Plotly's "bar" type wants center positions + explicit widths, not
  // raw bin edges — numpy.histogram() gives us N+1 edges for N counts.
  const centers = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
  const widths = counts.map((_, i) => edges[i + 1] - edges[i]);

  return (
    <div style={{ maxWidth: 800, margin: "1rem auto" }}>
      <Plot
        data={[
          {
            x: centers,
            y: counts,
            type: "bar",
            width: widths,
            marker: { color: "#2563eb" },
          },
        ]}
        layout={{
          title: { text: `Histogram: ${variable}` },
          autosize: true,
          height: 480,
          margin: { t: 40, r: 50, b: 80, l: 60 },
          xaxis: { title: { text: variable } },
          yaxis: { title: { text: "Pixel count" } },
          bargap: 0.02,
        }}
        style={{ width: "100%" }}
        useResizeHandler
        config={{ displaylogo: false, responsive: true }}
      />
      <p style={{ fontSize: "0.8rem", color: "#555", textAlign: "center" }}>
        Valid pixels: {data.valid_pixel_count?.toLocaleString()} · Mean:{" "}
        {data.mean?.toFixed(4)} · Std: {data.std?.toFixed(4)}
      </p>
    </div>
  );
}