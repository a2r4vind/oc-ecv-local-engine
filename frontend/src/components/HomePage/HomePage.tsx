import "./HomePage.css";

interface HomePageProps {
  onOpenWorkspace: () => void;
}

export default function HomePage({ onOpenWorkspace }: HomePageProps) {
  return (
    <div className="home-page">
      <div className="home-hero">
        <h1>OC-ECV Local Engine</h1>
        <p className="home-subtitle">
          Ocean Color &amp; Essential Climate Variables — local-first
          ingestion, processing, and visualization
        </p>
        <button type="button" className="home-cta" onClick={onOpenWorkspace}>
          Open Workspace
        </button>
        <p className="home-meta">
          Tauri + Python/FastAPI · xarray · MapLibre GL / deck.gl
        </p>
      </div>
    </div>
  );
}