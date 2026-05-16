import { useLocation } from "react-router-dom";
import { useInspection } from "../context/InspectionContext.jsx";

const PAGE_TITLES = {
  "/overview": ["INSPECTION_WORKSPACE", "System Overview"],
  "/ingestion": ["BATCH_INGESTION", "Image Ingestion"],
  "/defect-detection": ["DEFECT_DETECTION_VIEWER", "Defect Detection"],
  "/explainability": ["GRADCAM_ANALYSIS", "Explainability"],
  "/root-cause": ["ROOT_CAUSE_ENGINE", "Root Cause Analysis"],
  "/drift-monitoring": ["DRIFT_MONITOR", "Drift Monitoring"],
  "/synthetic-data": ["SYNTH_DATA_GEN", "Synthetic Data"],
  "/auto-retraining": ["AUTO_RETRAIN_LOOP", "Auto-Retraining"],
  "/logs": ["ARTIFACT_LOG", "Logs & Artifacts"],
  "/batch-inspection": ["SPATIAL_DEFECT_INTEL", "Batch Inspection"],

};

export default function Topbar({ overviewMode, setOverviewMode }) {
  const { pathname } = useLocation();
  const { metrics } = useInspection();
  const isOverviewRoute = pathname === "/overview";

  const [moduleId, title] = PAGE_TITLES[pathname] ?? ["MODULE", "AutoYield"];
  const vram = metrics?.model_metrics?.vram_gb;
  const vramLabel = vram != null ? `${vram} GB / 16 GB` : "12.4 GB / 16 GB";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-breadcrumb">
          <span>AUTOYIELD.AI</span>
          <span style={{ opacity: 0.4 }}>{">"}</span>
          <span style={{ color: "var(--text)", fontWeight: 700 }}>
            {title.toUpperCase()}
          </span>
        </div>
        <div
          style={{ width: 1, height: 16, background: "var(--stroke-major)" }}
        />
        <div className="topbar-title">// {moduleId}</div>
      </div>

      <div className="topbar-right">
        {isOverviewRoute && (
          <button
            type="button"
            className="topbar-mode-toggle"
            onClick={() =>
              setOverviewMode?.(
                overviewMode === "frontpage" ? "workspace" : "frontpage"
              )
            }
          >
            {overviewMode === "frontpage" ? "WORKSPACE" : "FRONT PAGE"}
          </button>
        )}

        <div className="vram-badge">
          <span className="material-symbols-rounded">memory</span>
          vRAM {vramLabel}
        </div>
        <div className="live-badge">Live Session</div>
      </div>
    </header>
  );
}
