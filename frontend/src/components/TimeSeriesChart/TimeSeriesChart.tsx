import { useRef } from "react";
import Plot from "react-plotly.js";
import type { NormalizedTimeSeries } from "../../utils/timeseries";
import ExportButton from "../ExportButton/ExportButton";
import { exportPlotToBlob } from "../../utils/chartExport";
import { saveBinaryFile, blobToUint8Array } from "../../utils/saveFile";
import type { ExportFormat } from "../../utils/mapExport";
interface TimeSeriesChartProps {
  data: NormalizedTimeSeries;
  variable: string;
  title: string;
}
export default function TimeSeriesChart({ data, variable, title }: TimeSeriesChartProps) {
  const graphDivRef = useRef<HTMLElement | null>(null);

  async function handleExport(format: ExportFormat) {
    if (!graphDivRef.current) throw new Error("Chart not ready");
    const blob = await exportPlotToBlob({ graphDiv: graphDivRef.current, format });
    const bytes = await blobToUint8Array(blob);
    await saveBinaryFile(bytes, {
      defaultFileName: `oc-ecv-timeseries-${variable}.${format === "jpeg" ? "jpg" : "png"}`,
      filterName: format === "jpeg" ? "JPEG Image" : "PNG Image",
      extensions: [format === "jpeg" ? "jpg" : "png"],
    });
  }

  const times = data.points.map((p) => p.time);
  const values = data.points.map((p) => p.value);
  const anomalies = data.points.map((p) => p.anomaly);

  return (
    <div className="chart-wrapper">
      <Plot
        data={[
          {
            x: times,
            y: values,
            type: "scatter",
            mode: "lines+markers",
            name: variable,
            line: { color: "#2563eb" },
            marker: { size: 6 },
            hovertemplate: `<b>%{x}</b><br>${variable}: %{y:.4f}<extra></extra>`,
          },
          {
            x: times,
            y: anomalies,
            type: "bar",
            name: "Anomaly (deviation from series mean)",
            marker: { color: "#f59e0b" },
            yaxis: "y2",
            opacity: 0.5,
            hovertemplate: `<b>%{x}</b><br>Anomaly: %{y:.4f}<extra></extra>`,
          },
        ]}
        layout={{
          title: { text: title },
          autosize: true,
          height: 480,
          margin: { t: 40, r: 50, b: 130, l: 50 },
          xaxis: {
            title: { text: "Time" },
            tickangle: -45,
            automargin: true,
          },
          yaxis: { title: { text: variable }, automargin: true },
          yaxis2: {
            title: { text: "Anomaly" },
            overlaying: "y",
            side: "right",
            automargin: true,
            tickformat: ".3f"
          },
          legend: { orientation: "h", y: -0.35 },
          // Day 30: groups both traces' tooltips into one shared box per
          // x-position, rather than two separately-floating boxes.
          hovermode: "x unified",
        }}
        
        style={{ width: "100%" }}
        useResizeHandler
        config={{ displaylogo: false, responsive: true }}
        onInitialized={(_fig, gd) => { graphDivRef.current = gd; }}
        onUpdate={(_fig, gd) => { graphDivRef.current = gd; }}
      />
      {data.seriesMean !== null && (
        <p style={{ fontSize: "0.8rem", color: "#555", textAlign: "center" }}>
          Series mean: {data.seriesMean.toFixed(4)}
        </p>
      )}
      <div style={{ display: "flex", justifyContent: "center", marginTop: "4px" }}>
        <ExportButton onExport={handleExport} label="Export Chart" />
      </div>
    </div>
  );
}
        