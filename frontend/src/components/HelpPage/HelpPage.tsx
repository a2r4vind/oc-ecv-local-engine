import "./HelpPage.css";

const STEPS = [
  {
    title: "1. Load a File",
    body: "Use the file uploader on the Process tab to ingest a local NetCDF, HDF, or GeoTIFF file (drag-and-drop or Browse Files).",
  },
  {
    title: "2. Select Parameters",
    body: "Pick a variable, draw or type a bounding box, and (for flat-grid files) a date range in the Query tab.",
  },
  {
    title: "3. Run Query",
    body: "Submit the query to compute statistics and render a colored raster on the map.",
  },
  {
    title: "4. Explore Time Series / Histogram / Scatter",
    body: "Switch tabs in the sidebar to run time-series, histogram, or scatter analyses against the same file.",
  },
  {
    title: "5. Export Results",
    body: "Use the export buttons above the map to save raw data (CSV/NetCDF) or georeferenced rasters (GeoTIFF).",
  },
  {
    title: "6. Review History",
    body: "Open the History tab to revisit and reload any past query.",
  },
];

export default function HelpPage() {
  return (
    <div className="help-page">
      <h1>System Instructions</h1>
      <p className="help-lede">
        Step-by-step guide to using the OC-ECV Local Engine workflow.
      </p>
      <div className="help-steps">
        {STEPS.map((s) => (
          <div className="help-step" key={s.title}>
            <h3>{s.title}</h3>
            <p>{s.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}