import "./TopNav.css";

export type TopTab = "home" | "process" | "about" | "help";

interface TopNavProps {
  active: TopTab;
  onChange: (tab: TopTab) => void;
  status?: string;
}

const TABS: { key: TopTab; label: string }[] = [
  { key: "home", label: "HOME" },
  { key: "process", label: "PROCESS" },
  { key: "about", label: "ABOUT" },
  { key: "help", label: "HELP" },
];

export default function TopNav({ active, onChange, status = "READY" }: TopNavProps) {
  return (
    <nav className="top-nav">
      <div className="top-nav-brand">OC-ECV Local Engine</div>
      <div className="top-nav-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={active === t.key ? "top-nav-tab active" : "top-nav-tab"}
            onClick={() => onChange(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="top-nav-status">{status}</div>
    </nav>
  );
}