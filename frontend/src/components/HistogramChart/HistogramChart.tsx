import { useRef } from "react";
import Plot from "react-plotly.js";
import type { HistogramResult } from "../../services/backendApi";
import ExportButton from "../ExportButton/ExportButton";
import { exportPlotToBlob } from "../../utils/chartExport";
import { saveBinaryFile, blobToUint8Array } from "../../utils/saveFile";
import type { ExportFormat } from "../../utils/mapExport";
interface HistogramChartProps {
  data: HistogramResult;
  variable: string;
}
export default function HistogramChart({ data, variable }: HistogramChartProps) {
  const graphDivRef = useRef<HTMLElement | null>(null);

  async function handleExport(format: ExportFormat) {
    if (!graphDivRef.current) throw new Error("Chart not ready");
    const blob = await exportPlotToBlob({ graphDiv: graphDivRef.current, format });
    const bytes = await blobToUint8Array(blob);
    await saveBinaryFile(bytes, {
      defaultFileName: `oc-ecv-histogram-${variable}.${format === "jpeg" ? "jpg" : "png"}`,
      filterName: format === "jpeg" ? "JPEG Image" : "PNG Image",
      extensions: [format === "jpeg" ? "jpg" : "png"],
    });
  }

  const edges = data.bin_edges ?? [];
  const counts = data.counts ?? [];
  // Plotly's "bar" type wants center positions + explicit widths, not
  // raw bin edges — numpy.histogram() gives us N+1 edges for N counts.
  const centers = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
  const widths = counts.map((_, i) => edges[i + 1] - edges[i]);
  // Day 30: exact bin range per bar — the bin center alone (Plotly's
  // default x hover value) doesn't convey the bin's width.
  const rangeLabels = counts.map(
    (_, i) => `${edges[i].toFixed(3)}–${edges[i + 1].toFixed(3)}`
  );

  return (
    <div className="chart-wrapper">
      <Plot
        data={[
          {
            x: centers,
            y: counts,
            type: "bar",
            width: widths,
            marker: { color: "#2563eb" },
            customdata: rangeLabels,
            hovertemplate: "Range: %{customdata}<br>Count: %{y}<extra></extra>",
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
        onInitialized={(_fig, gd) => { graphDivRef.current = gd; }}
        onUpdate={(_fig, gd) => { graphDivRef.current = gd; }}
      />
      <p style={{ fontSize: "0.8rem", color: "#555", textAlign: "center" }}>
        Valid pixels: {data.valid_pixel_count?.toLocaleString()} · Mean:{" "}
        {data.mean?.toFixed(4)} · Std: {data.std?.toFixed(4)}
      </p>
      <div style={{ display: "flex", justifyContent: "center", marginTop: "4px" }}>
        <ExportButton onExport={handleExport} label="Export Chart" />
      </div>
    </div>
  );
}
    