import "./AboutPage.css";

export default function AboutPage() {
  return (
    <div className="about-page">
      <h1>About OC-ECV Local Engine</h1>
      <p className="about-lede">
        A local-first desktop tool to ingest, process, and visualize Ocean
        Color &amp; Essential Climate Variable satellite data — combining
        NASA Giovanni's UI/UX with SeaDAS-style offline processing.
      </p>

      <div className="about-badges">
        <span className="about-badge">Tauri v2 + React</span>
        <span className="about-badge">Python / FastAPI</span>
        <span className="about-badge">xarray / netCDF4 / rasterio</span>
      </div>

      <h2>Development</h2>
      <div className="about-card">
        <p>Solo development project — MVP roadmap across five phases.</p>
      </div>

      <h2>Roadmap</h2>
      <ul className="about-list">
        <li>Sea Ice Concentration ECV (post-MVP)</li>
        <li>TSM / SSC ECV coverage</li>
        <li>Advanced SeaDAS-style raw processing chains</li>
        <li>Multi-dataset comparison (MODIS vs Sentinel vs VIIRS)</li>
      </ul>
    </div>
  );
}