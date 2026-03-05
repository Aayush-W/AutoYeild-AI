import { useLocation } from "react-router-dom";
import { useInspection } from "../context/InspectionContext.jsx";

const PAGE_TITLES = {
  "/overview": "System Overview",
  "/ingestion": "Image Ingestion",
  "/defect-detection": "Defect Detection",
  "/explainability": "Explainability",
  "/root-cause": "Root Cause Analysis",
  "/drift-monitoring": "Drift Monitoring",
  "/synthetic-data": "Synthetic Data",
  "/auto-retraining": "Auto-Retraining",
  "/logs": "Logs & Artifacts",
};

export default function Topbar() {
  const { pathname } = useLocation();
  const { metrics } = useInspection();

  const title = PAGE_TITLES[pathname] ?? "AutoYield";

  // Attempt to show a rough vRAM figure from model metrics if available
  const vram = metrics?.model_metrics?.vram_gb;
  const vramLabel = vram != null ? `${vram} GB / 16 GB` : "12.4 GB / 16 GB";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-title">{title}</div>
      </div>

      <div className="topbar-right">
        {/* vRAM badge */}
        <div className="vram-badge">
          <span className="material-symbols-rounded">memory</span>
          vRAM {vramLabel}
        </div>

        {/* Live session badge */}
        <div className="live-badge">Live Session</div>
      </div>
    </header>
  );
}
