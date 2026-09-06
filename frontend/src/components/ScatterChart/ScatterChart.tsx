import { useLayoutEffect, useRef } from "react";
import Plot from "react-plotly.js";
import Plotly from "plotly.js-dist-min";
import type { ScatterResult } from "../../services/backendApi";
import ExportButton from "../ExportButton/ExportButton";
import { exportPlotToBlob } from "../../utils/chartExport";
import { saveBinaryFile, blobToUint8Array } from "../../utils/saveFile";
import { loseAllWebGLContextsIn } from "../../utils/webglCleanup";
import type { ExportFormat } from "../../utils/mapExport";
interface ScatterChartProps {
  data: ScatterResult;
}
export default function ScatterChart({ data }: ScatterChartProps) {
  const graphDivRef = useRef<HTMLElement | null>(null);
  
  // Day 45 correction: switched from useEffect to useLayoutEffect.
  // react-plotly.js's own newPlot()/purge() calls happen synchronously
  // during React's commit phase (componentDidMount/componentWillUnmount
  // timing), not deferred like a passive effect. A plain useEffect
  // cleanup here ran AFTER the new ScatterChart instance's own
  // componentDidMount had already called Plotly.newPlot() and created
  // its fresh WebGL context — so our forced context-loss call was
  // racing against (and often losing to) the next mount instead of
  // running before it. Reproduced directly: repeated scatterRunId-keyed
  // remounts started throwing "too many active WebGL contexts" only
  // after ~6-7 cycles, consistent with a slow backlog under this
  // environment's WebKitGTK/Zink software rendering (already a known
  // constraint elsewhere in this project) rather than an immediate
  // failure. useLayoutEffect runs synchronously in the same commit as
  // the old instance's unmount, before the new instance's mount effects
  // fire, closing that gap.
  useLayoutEffect(() => {
    return () => {
      const el = graphDivRef.current;
      if (!el) return;
      Plotly.purge(el);
      loseAllWebGLContextsIn(el as unknown as HTMLElement);
    };
  }, []);
  
 
  async function handleExport(format: ExportFormat) {
    if (!graphDivRef.current) throw new Error("Chart not ready");
    const blob = await exportPlotToBlob({ graphDiv: graphDivRef.current, format });
    const bytes = await blobToUint8Array(blob);
    await saveBinaryFile(bytes, {
      defaultFileName: `oc-ecv-scatter-${data.variable_x}-vs-${data.variable_y}.${format === "jpeg" ? "jpg" : "png"}`,
      filterName: format === "jpeg" ? "JPEG Image" : "PNG Image",
      extensions: [format === "jpeg" ? "jpg" : "png"],
    });
  }

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
            hovertemplate: `${data.variable_x}: %{x:.4f}<br>${data.variable_y}: %{y:.4f}<extra></extra>`,
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
        onInitialized={(_fig, gd) => { graphDivRef.current = gd; }}
        onUpdate={(_fig, gd) => { graphDivRef.current = gd; }}
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
      <div style={{ display: "flex", justifyContent: "center", marginTop: "4px" }}>
        <ExportButton onExport={handleExport} label="Export Chart" />
      </div>
    </div>
  );
}