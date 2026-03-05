import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

const DEFECT_DESCRIPTIONS = {
  scratch: "Linear mechanical damage on wafer surface.",
  particle: "Foreign material deposition causing contamination.",
  crack: "Structural fracture or stress-induced cracking.",
  clean: "No defect detected on wafer surface.",
  normal: "No defect detected on wafer surface.",
  random: "Scattered defect points across the surface.",
  local: "Localized defect cluster in a specific region.",
  edge_ring: "Ring-shaped defects near the wafer edge.",
  center: "Defects concentrated near the wafer center.",
};

const SEVERITY_CHIP = {
  "Critical": "danger",
  "High": "warn",
  "Medium": "warn",
  "Low": "info",
  "Minimal": "",
};

export default function DefectDetection() {
  const { inspection, history } = useInspection();
  const navigate = useNavigate();
  const hasData = Boolean(inspection);

  const label = hasData ? inspection.defect_class : null;
  const normalKey = label?.toLowerCase().replace(/[\s-]+/g, "_").trim();
  const description = DEFECT_DESCRIPTIONS[normalKey] ?? "Defect description unavailable.";
  const severity = inspection?.reasoning?.severity_assessment ?? inspection?.severity ?? "Medium";
  const severityChip = SEVERITY_CHIP[severity] ?? "warn";
  const confidence = hasData ? Math.round(inspection.confidence * 100) : null;

  // Historical comparison: last 4 entries from history
  const histBatches = history.length
    ? [...history].reverse().slice(0, 4)
    : [];

  return (
    <>
      {/* Header row */}
      <div className="engine-banner">
        <div className="engine-banner-left">
          <div>
            <div className="engine-title" style={{ fontSize: 13 }}>
              {hasData
                ? `Wafer ID: ${inspection.inspection_id}`
                : "Detection Inference"}
            </div>
            <div className="engine-subtitle">
              {hasData
                ? `Batch #${inspection.inspection_id?.split("-")[1] ?? "—"} • ${inspection.timestamp}`
                : "Run an analysis in Image Ingestion to see results"}
            </div>
          </div>
        </div>
        {hasData && (
          <div style={{ display: "flex", gap: 10 }}>
            <span className={`chip ${severityChip}`}>{severity}</span>
            <span className="chip info">{inspection.inference_time_ms} ms</span>
          </div>
        )}
      </div>

      {!hasData && (
        <div className="alert info">
          <div className="alert-icon">
            <span className="material-symbols-rounded" style={{ color: "var(--accent)" }}>
              info
            </span>
          </div>
          <div className="alert-body">
            <div className="alert-title">No inspection data yet</div>
            <div className="alert-detail">
              Upload a wafer image in{" "}
              <button
                className="btn sm"
                style={{ display: "inline-flex", padding: "2px 8px" }}
                onClick={() => navigate("/ingestion")}
              >
                Image Ingestion
              </button>{" "}
              to run a defect analysis.
            </div>
          </div>
        </div>
      )}

      {hasData && (
        <div className="grid-2">
          {/* Original scan */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>
              <span className="material-symbols-rounded">image</span>
              Original SEM Scan
            </div>
            <div className="image-frame">
              <img src={inspection.input_image} alt="Wafer scan" />
            </div>
          </div>

          {/* Inference result */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>
              <span className="material-symbols-rounded">analytics</span>
              Inference Result
            </div>

            <div className="inference-result-panel">
              <div>
                <div className="inference-class-name" style={{ textTransform: "capitalize" }}>
                  {label}
                </div>
                <div className="stat-foot" style={{ marginTop: 4 }}>{description}</div>
              </div>

              <div className="inference-row">
                <div className="inference-stat">
                  <div className="inference-stat-label">Severity</div>
                  <span className={`chip ${severityChip}`}>{severity}</span>
                </div>
                <div className="inference-stat">
                  <div className="inference-stat-label">Inference Time</div>
                  <div className="inference-stat-value">{inspection.inference_time_ms} ms</div>
                </div>
                {inspection.drift_detected && (
                  <div className="inference-stat">
                    <div className="inference-stat-label">Drift</div>
                    <span className="chip warn">Detected</span>
                  </div>
                )}
              </div>

              {/* Confidence bar */}
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 6,
                  }}
                >
                  <span className="stat-foot">Confidence Score</span>
                  <span style={{ fontWeight: 700, fontSize: 13 }}>{confidence}%</span>
                </div>
                <div className="progress thick">
                  <span style={{ width: `${confidence}%` }} />
                </div>
              </div>

              {/* Candidate classes */}
              <div>
                <div className="card-title" style={{ marginBottom: 10 }}>
                  <span className="material-symbols-rounded">format_list_numbered</span>
                  Candidate Classes
                </div>
                <div className="candidate-list">
                  {(inspection.top_predictions ?? []).map((pred, i) => (
                    <div className="candidate-item" key={i}>
                      <span
                        className="candidate-label"
                        style={{ textTransform: "capitalize" }}
                      >
                        {i + 1}. {pred.label}
                      </span>
                      <div className="progress" style={{ flex: 1 }}>
                        <span style={{ width: `${Math.round(pred.prob * 100)}%` }} />
                      </div>
                      <span className="candidate-pct">
                        {Math.round(pred.prob * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Historical Comparison */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span className="material-symbols-rounded">compare</span>
            Historical Comparison
          </div>
        </div>
        {histBatches.length > 0 ? (
          <div className="history-comparison">
            {histBatches.map((batch, i) => (
              <div
                key={i}
                className={`history-batch${i === 0 ? " current" : ""}`}
              >
                <div className="history-batch-id">
                  {i === 0 ? "CURRENT" : `BATCH #${i}`}
                </div>
                <div
                  className="history-batch-class"
                  style={{ textTransform: "capitalize" }}
                >
                  {batch.defect_class}
                </div>
                <div className="history-batch-conf">
                  {Math.round(batch.confidence * 100)}% conf
                  {batch.drift_detected ? " • drift" : ""}
                </div>
                <div className="stat-foot" style={{ marginTop: 4, fontSize: 10 }}>
                  {batch.timestamp}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="stat-foot" style={{ padding: "8px 0" }}>
            No batch history available yet.
          </div>
        )}
      </div>

      {/* Model Engine panel */}
      <div className="card" style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 38, height: 38,
              borderRadius: "var(--r-sm)",
              background: "rgba(43,140,238,0.15)",
              display: "grid", placeItems: "center",
            }}
          >
            <span className="material-symbols-rounded" style={{ color: "var(--accent)" }}>memory</span>
          </div>
          <div>
            <div style={{ fontWeight: 700, fontFamily: "var(--font-head)", fontSize: 14 }}>
              YieldSense v4.2
            </div>
            <div className="stat-foot">Model Engine</div>
          </div>
        </div>
        <div className="divider" style={{ width: 1, height: 36, background: "var(--stroke)" }} />
        <div>
          <div className="stat-foot">Last Trained</div>
          <div style={{ fontWeight: 600, fontSize: 12 }}>
            {/* try to show last retrain from history */}
            {histBatches.find((b) => b.retrain_result)
              ? histBatches.find((b) => b.retrain_result).timestamp
              : "2 days ago"}
          </div>
        </div>
        {hasData && (
          <>
            <div className="divider" style={{ width: 1, height: 36, background: "var(--stroke)" }} />
            <div>
              <div className="stat-foot">Triage Priority</div>
              <div className={`chip ${inspection.triage?.priority === "high" ? "warn" : "info"}`}>
                {inspection.triage?.priority ?? "normal"}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
