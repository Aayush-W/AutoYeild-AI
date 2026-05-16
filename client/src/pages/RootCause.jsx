import { useEffect, useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

function ChecklistSection({ title, items, onToggle }) {
  if (!items?.length) {
    return null;
  }

  return (
    <div style={{ marginBottom: 14 }}>
      <div className="stat-foot" style={{ marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        {title}
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className="insight-action"
            onClick={() => onToggle?.(item.id)}
            style={{
              border: "1px solid var(--stroke)",
              background: item.checked ? "var(--bg-1)" : "transparent",
              width: "100%",
              textAlign: "left",
              cursor: "pointer",
            }}
          >
            <span className="material-symbols-rounded">
              {item.checked ? "check_box" : "check_box_outline_blank"}
            </span>
            <div
              className="insight-action-text"
              style={{
                textDecoration: item.checked ? "line-through" : "none",
                opacity: item.checked ? 0.7 : 1,
              }}
            >
              {item.label}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function RootCause() {
  const { inspection } = useInspection();
  const navigate = useNavigate();
  const hasData = Boolean(inspection);
  const reasoning = inspection?.reasoning ?? {};
  const rootCauseUi = reasoning.root_cause_ui ?? {};
  const summary = rootCauseUi.summary_paragraph ?? reasoning.summary ?? reasoning.cause_summary ?? "";
  const probableRootCause = rootCauseUi.probable_root_cause ?? {};
  const correctiveAction = rootCauseUi.recommended_corrective_action ?? {};
  const [workOrderSections, setWorkOrderSections] = useState([]);
  const [isAcknowledged, setIsAcknowledged] = useState(false);

  const severityMap = {
    Critical: "danger",
    High: "warn",
    Medium: "warn",
    Low: "info",
    Minimal: "",
  };
  const chipVariant = severityMap[reasoning.severity_assessment] ?? "warn";
  const hasWorkOrder = workOrderSections.length > 0;
  const completedCount = workOrderSections.reduce(
    (total, section) => total + section.items.filter((item) => item.checked).length,
    0
  );
  const totalCount = workOrderSections.reduce((total, section) => total + section.items.length, 0);

  useEffect(() => {
    setWorkOrderSections([]);
    setIsAcknowledged(false);
  }, [inspection?.inspection_id]);

  const handleCreateWorkOrder = () => {
    const nextSections = (correctiveAction.sections ?? []).map((section, sectionIndex) => ({
      ...section,
      items: (section.items ?? []).map((item, itemIndex) => ({
        id: `${sectionIndex}-${itemIndex}`,
        label: item,
        checked: false,
      })),
    }));
    setWorkOrderSections(nextSections);
    setIsAcknowledged(false);
  };

  const handleToggleChecklistItem = (itemId) => {
    setWorkOrderSections((prev) =>
      prev.map((section) => ({
        ...section,
        items: section.items.map((item) =>
          item.id === itemId ? { ...item, checked: !item.checked } : item
        ),
      }))
    );
  };

  const handleAcknowledge = () => {
    if (!hasWorkOrder) {
      return;
    }
    setIsAcknowledged(true);
  };

  return (
    <>
      <div className="section-header">
        <div>
          <div className="section-title">Root Cause Analysis</div>
          <div className="section-sub">Rule-first root cause analysis with structured Gemini enrichment</div>
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

      <div className="card">
        <div className="card-title" style={{ marginBottom: 14 }}>
          <span className="material-symbols-rounded">data_object</span>
          Structured Evidence Input
        </div>
        <div className="grid-4" style={{ gap: 16 }}>
          {[
            { label: "Defect Type", value: hasData ? inspection.defect_class : "-" },
            { label: "Confidence", value: hasData ? `${Math.round(inspection.confidence * 100)}%` : "-" },
            { label: "Inspection ID", value: hasData ? inspection.inspection_id : "-" },
            { label: "Timestamp", value: hasData ? inspection.timestamp?.split(" ")[1] ?? "-" : "-" },
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

      <div className="alert warn">
        <div className="alert-icon">
          <span className="material-symbols-rounded" style={{ color: "var(--warning)" }}>warning</span>
        </div>
        <div className="alert-body">
          <div className="alert-title">Risk Assessment</div>
          <div className="alert-detail">
            {reasoning.severity_assessment
              ? `${reasoning.severity_assessment} risk based on current defect pattern.`
              : "Immediate engineering review recommended."}
          </div>
        </div>
        <span className={`chip ${chipVariant}`}>
          {reasoning.severity_assessment ? `${reasoning.severity_assessment} Risk` : "Medium Risk"}
        </span>
      </div>

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
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>manage_search</span>
            Probable Root Cause
          </div>
          <div className="stat-foot" style={{ marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Root Cause Identified
          </div>
          <div className="reasoning-panel-body" style={{ marginBottom: 12 }}>
            {probableRootCause.root_cause_identified ?? reasoning.probable_root_cause ?? "Root cause pending review."}
          </div>
          {(probableRootCause.evidence_signals ?? []).length > 0 && (
            <>
              <div className="stat-foot" style={{ marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Evidence Supporting This Conclusion
              </div>
              <ul style={{ margin: "0 0 12px 18px", padding: 0, color: "var(--secondary)", fontSize: 12, lineHeight: 1.6 }}>
                {probableRootCause.evidence_signals.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </>
          )}
          <div className="reasoning-panel-body">
            {probableRootCause.explanation ?? reasoning.pattern_analysis ?? "Supporting evidence is not available."}
          </div>
        </div>

        <div className="reasoning-panel">
        <div className="reasoning-panel-title">
          <span className="material-symbols-rounded" style={{ fontSize: 14 }}>build</span>
          Recommended Corrective Action
        </div>
          {hasWorkOrder ? (
            <div>
              <div className="stat-foot" style={{ marginBottom: 12 }}>
                {completedCount}/{totalCount} tasks completed
                {isAcknowledged ? " · acknowledged" : ""}
              </div>
              {workOrderSections.map((section, index) => (
                <ChecklistSection
                  key={index}
                  title={section.title}
                  items={section.items}
                  onToggle={handleToggleChecklistItem}
                />
              ))}
            </div>
          ) : (
            <div className="reasoning-panel-body">
              Click <strong>Create Work Order</strong> to generate the corrective-action checklist.
            </div>
          )}
          <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
            <button className="btn sm" onClick={handleAcknowledge} disabled={!hasWorkOrder}>
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>check</span>
              {isAcknowledged ? "Acknowledged" : "Mark Acknowledged"}
            </button>
            <button className="btn primary sm" onClick={handleCreateWorkOrder}>
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
