import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

export default function AutoRetraining() {
  const { history, inspection } = useInspection();
  const navigate = useNavigate();
  const retrainCandidates = history.filter((item) => item.drift_detected);
  const latestTrigger = retrainCandidates.length
    ? retrainCandidates[retrainCandidates.length - 1]
    : null;

  // Check if the latest inspection has retrain results
  const retrainResult = inspection?.retrain_result ?? null;

  return (
    <>
      <div className="section-header">
        <div>
          <div className="section-title">Auto-Retraining</div>
          <div className="section-sub">Automated model retraining readiness and trigger log</div>
        </div>
        <button className="btn primary sm" onClick={() => navigate("/ingestion")}>
          <span className="material-symbols-rounded" style={{ fontSize: 14 }}>add</span>
          New Analysis
        </button>
      </div>

      {/* Metric cards */}
      <div className="grid-4">
        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">pending</span>
            Retrain Queue
          </div>
          <div className="metric-value">{retrainCandidates.length}</div>
          <div className="metric-foot">drift events pending</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">check_circle</span>
            Status
          </div>
          <div className="metric-value" style={{ fontSize: 16 }}>
            {retrainResult ? "Retrained" : "Standby"}
          </div>
          <div className="metric-foot">
            {retrainResult ? (
              <span className="chip">Done</span>
            ) : (
              <span className="chip info">Idle</span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">bolt</span>
            Synthetics Used
          </div>
          <div className="metric-value">{inspection?.synthetic_count ?? 0}</div>
          <div className="metric-foot">this session</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">auto_mode</span>
            Auto Retrain
          </div>
          <div className="metric-value" style={{ fontSize: 16 }}>
            {inspection?.auto_retrain ? "On" : "Off"}
          </div>
          <div className="metric-foot">configured in ingestion</div>
        </div>
      </div>

      <div className="grid-2">
        {/* Latest trigger */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">schedule</span>
            Latest Trigger
          </div>
          {latestTrigger ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div>
                <div className="stat-foot">Defect Class</div>
                <div style={{ fontWeight: 600, fontSize: 14, textTransform: "capitalize", marginTop: 3 }}>
                  {latestTrigger.defect_class}
                </div>
              </div>
              <div className="stat-foot">{latestTrigger.timestamp}</div>
              <div className="progress thick">
                <span style={{ width: `${Math.round(latestTrigger.confidence * 100)}%` }} />
              </div>
              <div className="stat-foot">
                Confidence: {Math.round(latestTrigger.confidence * 100)}%
              </div>
              <span className="chip warn" style={{ alignSelf: "flex-start" }}>Drift Triggered</span>
            </div>
          ) : (
            <div className="stat-foot">No retraining triggers yet. System is stable.</div>
          )}
        </div>

        {/* Retrain Result */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">model_training</span>
            Latest Retrain Result
          </div>
          {retrainResult ? (
            <pre
              style={{
                background: "rgba(7,14,26,0.8)",
                borderRadius: "var(--r-md)",
                padding: "12px",
                fontSize: 11,
                color: "var(--muted)",
                whiteSpace: "pre-wrap",
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {JSON.stringify(retrainResult, null, 2)}
            </pre>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="stat-foot">No retrain has executed yet this session.</div>
              <div
                className="advisory-banner"
                style={{ marginTop: 8 }}
              >
                <span className="material-symbols-rounded">info</span>
                <div>
                  <div className="advisory-label">How to trigger</div>
                  <div className="advisory-text">
                    Enable &ldquo;Auto Retrain&rdquo; in the Engine Parameters panel on the
                    Image Ingestion page, then upload a wafer scan. Retraining fires
                    automatically after synthetic data generation.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Suggested Action */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 10 }}>
          <span className="material-symbols-rounded">lightbulb</span>
          Suggested Workflow
        </div>
        <div className="stat-foot" style={{ lineHeight: 1.7 }}>
          After drift-triggered synthetic data generation, validate the new samples on the
          Synthetic Data page, then enable Auto Retrain in Engine Parameters before the next
          ingestion run. Monitor accuracy delta in the Logs &amp; Artifacts page post-retrain.
        </div>
        <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
          <button className="btn" onClick={() => navigate("/synthetic-data")}>
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>auto_awesome_mosaic</span>
            View Synthetics
          </button>
          <button className="btn primary" onClick={() => navigate("/ingestion")}>
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>upload_file</span>
            Go to Ingestion
          </button>
        </div>
      </div>
    </>
  );
}
