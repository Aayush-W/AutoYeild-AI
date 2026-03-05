import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

export default function RootCause() {
  const { inspection } = useInspection();
  const navigate = useNavigate();
  const hasData = Boolean(inspection);
  const reasoning = inspection?.reasoning ?? {};
  const summary = reasoning.summary ?? reasoning.cause_summary ?? "";

  const severityMap = {
    Critical: "danger",
    High: "warn",
    Medium: "warn",
    Low: "info",
    Minimal: "",
  };
  const chipVariant = severityMap[reasoning.severity_assessment] ?? "warn";

  return (
    <>
      {/* Section header */}
      <div className="section-header">
        <div>
          <div className="section-title">Root Cause Analysis</div>
          <div className="section-sub">LLM-powered defect origin insights</div>
        </div>
        {hasData && (
          <span className="chip info" style={{ textTransform: "capitalize" }}>
            {inspection.defect_class}
          </span>
        )}
      </div>

      {!hasData && (
        <div className="alert info">
          <div className="alert-icon">
            <span className="material-symbols-rounded" style={{ color: "var(--accent)" }}>info</span>
          </div>
          <div className="alert-body">
            <div className="alert-title">No inspection data</div>
            <div className="alert-detail">
              <button className="btn sm" style={{ display: "inline-flex", padding: "2px 8px" }} onClick={() => navigate("/ingestion")}>
                Run an analysis
              </button>{" "}
              to generate root cause insights.
            </div>
          </div>
        </div>
      )}

      {/* Evidence Input */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 14 }}>
          <span className="material-symbols-rounded">data_object</span>
          Structured Evidence Input
        </div>
        <div className="grid-4" style={{ gap: 16 }}>
          {[
            { label: "Defect Type", value: hasData ? inspection.defect_class : "—" },
            { label: "Confidence", value: hasData ? `${Math.round(inspection.confidence * 100)}%` : "—" },
            { label: "Inspection ID", value: hasData ? inspection.inspection_id : "—" },
            { label: "Timestamp", value: hasData ? inspection.timestamp?.split(" ")[1] ?? "—" : "—" },
          ].map((stat) => (
            <div key={stat.label}>
              <div className="stat-foot">{stat.label}</div>
              <div style={{ fontWeight: 600, fontSize: 13, marginTop: 4, textTransform: "capitalize" }}>{stat.value}</div>
            </div>
          ))}
        </div>
        <div className="advisory-banner" style={{ marginTop: 14 }}>
          <span className="material-symbols-rounded">shield</span>
          <div>
            <div className="advisory-label">Privacy Note</div>
            <div className="advisory-text">Only structured evidence is passed to the LLM. Raw wafer images are never sent.</div>
          </div>
        </div>
      </div>

      {/* Risk Assessment */}
      <div className="alert warn">
        <div className="alert-icon">
          <span className="material-symbols-rounded" style={{ color: "var(--warning)" }}>warning</span>
        </div>
        <div className="alert-body">
          <div className="alert-title">Risk Assessment</div>
          <div className="alert-detail">
            {reasoning.severity_assessment
              ? `${reasoning.severity_assessment} risk based on current defect pattern.`
              : "2–5% yield loss if uncorrected. Immediate inspection recommended."}
          </div>
        </div>
        <span className={`chip ${chipVariant}`}>
          {reasoning.severity_assessment ? `${reasoning.severity_assessment} Risk` : "Medium Risk"}
        </span>
      </div>

      {/* GenAI Summary */}
      {summary && (
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>auto_awesome</span>
            GenAI Summary
          </div>
          <div className="reasoning-panel-body">{summary}</div>
          {reasoning.genai_note && (
            <div className="stat-foot" style={{ marginTop: 8 }}>{reasoning.genai_note}</div>
          )}
        </div>
      )}

      <div className="grid-2">
        {/* Root Cause */}
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>manage_search</span>
            Probable Root Cause
          </div>
          <div className="reasoning-panel-body">
            {reasoning.probable_root_cause ??
              "Mechanical contact during wafer handling or transport. Likely caused by improper end-effector alignment or debris on handling equipment."}
          </div>
          <div className="stat-foot" style={{ marginTop: 8 }}>
            {reasoning.pattern_analysis
              ? `Pattern: ${reasoning.pattern_analysis}`
              : "Affected process: Wafer Transport & Handling"}
          </div>
        </div>

        {/* Corrective Action */}
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>build</span>
            Recommended Corrective Action
          </div>
          <div className="reasoning-panel-body">
            {reasoning.recommended_action ??
              "Inspect and recalibrate robotic handler end-effectors. Clean all contact surfaces. Verify vacuum chuck condition and alignment. Schedule preventive maintenance."}
          </div>
          <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
            <button className="btn sm">
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>check</span>
              Mark Acknowledged
            </button>
            <button className="btn primary sm">
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>assignment_add</span>
              Create Work Order
            </button>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "center" }}>
        <button className="btn" onClick={() => navigate("/ingestion")}>
          <span className="material-symbols-rounded" style={{ fontSize: 15 }}>replay</span>
          Re-run Analysis
        </button>
      </div>
    </>
  );
}
