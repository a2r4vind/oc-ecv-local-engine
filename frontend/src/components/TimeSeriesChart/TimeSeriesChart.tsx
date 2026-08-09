import Plot from "react-plotly.js";
import type { NormalizedTimeSeries } from "../../utils/timeseries";

interface TimeSeriesChartProps {
  data: NormalizedTimeSeries;
  variable: string;
  title: string;
}

export default function TimeSeriesChart({ data, variable, title }: TimeSeriesChartProps) {
  const times = data.points.map((p) => p.time);
  const values = data.points.map((p) => p.value);
  const anomalies = data.points.map((p) => p.anomaly);

  return (
    <div style={{ maxWidth: 800, margin: "1rem auto" }}>
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
          },
          {
            x: times,
            y: anomalies,
            type: "bar",
            name: "Anomaly (deviation from series mean)",
            marker: { color: "#f59e0b" },
            yaxis: "y2",
            opacity: 0.5,
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
          yaxis: { title: { text: variable } },
          yaxis2: {
            title: { text: "Anomaly" },
            overlaying: "y",
            side: "right",
          },
          legend: { orientation: "h", y: -0.35 },
        }}
        
        style={{ width: "100%" }}
        useResizeHandler
        config={{ displaylogo: false, responsive: true }}
      />
      {data.seriesMean !== null && (
        <p style={{ fontSize: "0.8rem", color: "#555", textAlign: "center" }}>
          Series mean: {data.seriesMean.toFixed(4)}
        </p>
      )}
    </div>
  );
}