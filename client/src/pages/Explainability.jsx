import { useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

function ExplainabilityBlock({ title, icon, section, numbered = false }) {
  const bullets = section?.bullets ?? [];
  const explanation = section?.explanation ?? [];
  const steps = section?.steps ?? [];

  return (
    <div style={{ marginBottom: 18, paddingBottom: 14, borderBottom: "1px solid var(--stroke)" }}>
      <div className="card-title" style={{ marginBottom: 8 }}>
        <span className="material-symbols-rounded">{icon}</span>
        {title}
      </div>
      {bullets.length > 0 && (
        <ul style={{ fontSize: 12, color: "var(--secondary)", lineHeight: 1.6, paddingLeft: 20, margin: "0 0 10px 0" }}>
          {bullets.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      )}
      {explanation.length > 0 && (
        <div style={{ display: "grid", gap: 6 }}>
          {explanation.map((line, index) => (
            <div key={index} style={{ fontSize: 12, color: "var(--secondary)", lineHeight: 1.6 }}>
              {line}
            </div>
          ))}
        </div>
      )}
      {steps.length > 0 && (
        <div style={{ display: "grid", gap: 8 }}>
          {steps.map((step, index) => (
            <div key={index} className="insight-action">
              <span className="material-symbols-rounded">
                {numbered ? "format_list_numbered" : "select_check_box"}
              </span>
              <div className="insight-action-text">{numbered ? `${index + 1}. ${step}` : step}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Explainability() {
  const { inspection } = useInspection();
  const navigate = useNavigate();
  const hasData = Boolean(inspection);
  const [showOverlay, setShowOverlay] = useState(true);
  const [sideBySide, setSideBySide] = useState(true);
  const [opacity, setOpacity] = useState(0.7);

  const confidence = hasData ? Math.round(inspection.confidence * 100) : null;
  const reasoning = inspection?.reasoning ?? {};
  const explainability = inspection?.explainability_analysis ?? inspection?.ai_insight ?? null;
  const heatmapAnalysis = inspection?.heatmap_analysis ?? inspection?.triage ?? {};
  const meta = explainability?.metadata ?? {};

  const predictionReasoning = explainability?.prediction_reasoning ?? { bullets: [], explanation: [] };
  const heatmapInterpretation = explainability?.heatmap_interpretation ?? { bullets: [], explanation: [] };
  const defectPatternContext = explainability?.defect_pattern_context ?? { bullets: [], explanation: [] };
  const confidenceAnalysis = explainability?.confidence_analysis ?? { bullets: [], explanation: [] };
  const driftImpact = explainability?.drift_impact ?? { bullets: [], explanation: [] };
  const engineeringInterpretation = explainability?.engineering_interpretation ?? { bullets: [], explanation: [] };
  const recommendedSteps = explainability?.recommended_investigation_steps ?? [];

  const Toggle = ({ checked, onChange, label }) => (
    <div className="param-row" style={{ paddingBottom: 0, borderBottom: "none" }}>
      <span className="param-label">{label}</span>
      <label className="toggle-switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className="toggle-track" />
      </label>
    </div>
  );

  return (
    <>
      <div className="section-header">
        <div>
          <div className="section-title">GradCAM Analysis</div>
          <div className="section-sub">
            // Deep-dive diagnostic interface · AI attention maps and convolutional explainability
          </div>
        </div>
        {hasData && (
          <span className="chip info">
            {inspection.defect_class && (
              <span style={{ textTransform: "uppercase" }}>{inspection.defect_class}</span>
            )}
            &nbsp;· {confidence}% CONF
          </span>
        )}
      </div>

      {!hasData && (
        <div className="alert info">
          <div className="alert-icon">
            <span className="material-symbols-rounded" style={{ color: "var(--accent-blue)", fontSize: 18 }}>info</span>
          </div>
          <div className="alert-body">
            <div className="alert-title">// No inspection data</div>
            <div className="alert-detail">
              Run an analysis first in{" "}
              <button className="btn sm" style={{ display: "inline-flex", padding: "2px 8px" }}
                onClick={() => navigate("/ingestion")}>
                Image Ingestion
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid-2">
        <div className="model-status-widget" style={{ flexDirection: "column", alignItems: "flex-start", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
            <div className="engine-status-dot" />
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Active Model Status</div>
          </div>
          <div className="model-status-name">DefectNet-v4.2-TRT</div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Target Layer</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", marginTop: 2 }}>
                {meta.target_layer ?? "M2_Cu"}
              </div>
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Lot ID</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", marginTop: 2 }}>
                {meta.lot_id ?? inspection?.inspection_id ?? "N/A"}
              </div>
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Process Tool</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", marginTop: 2 }}>
                {meta.inspection_tool ?? "Litho-04"}
              </div>
            </div>
          </div>
          <div className="model-status-badge">ACTIVE</div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">monitor_heart</span>
              FEATURE DRIFT MONITOR
            </div>
            <span className={`chip ${inspection?.drift_detected ? "warn" : "success"}`}>
              {inspection?.drift_detected ? "WATCH" : "STABLE"}
            </span>
          </div>
          <div style={{ height: 80, display: "flex", alignItems: "flex-end", gap: 3 }}>
            {[30, 42, 38, 55, 48, 60, 72, 65, 80, 74, 88, 78, 85, 92, 78, 68, 74, 80, 76, 72, 68, 85, 90, 95].map((v, i) => (
              <div key={i} style={{
                flex: 1,
                height: `${v}%`,
                background: v > 80 ? "var(--accent)" : v > 60 ? "var(--accent-warn)" : "rgba(0,0,0,0.12)",
                borderRadius: 0,
              }} title={`${v}%`} />
            ))}
          </div>
          <div className="stat-foot" style={{ marginTop: 8 }}>
            {driftImpact.bullets?.[0] ?? "// Focus drift score over last 24 exposures"}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: 14 }}>
          <span className="material-symbols-rounded">tune</span>
          VISUALIZATION CONTROLS
        </div>
        <div style={{ display: "grid", gap: 12 }}>
          <Toggle checked={showOverlay} onChange={setShowOverlay} label="show_heatmap_overlay" />
          <Toggle checked={sideBySide} onChange={setSideBySide} label="side_by_side_comparison" />
          <div className="param-row" style={{ borderBottom: "none", paddingBottom: 0 }}>
            <span className="param-label">overlay_opacity</span>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input
                type="range" min={0} max={100}
                value={Math.round(opacity * 100)}
                onChange={(e) => setOpacity(Number(e.target.value) / 100)}
                style={{ width: 120, accentColor: "var(--text)" }}
              />
              <span className="stat-foot">{Math.round(opacity * 100)}%</span>
            </div>
          </div>
        </div>
      </div>

      <div className={sideBySide ? "grid-2" : ""}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">image</span>
            AI ATTENTION MAP · ORIGINAL SEM
          </div>
          {hasData ? (
            <div className="image-frame">
              <img src={inspection.input_image} alt="Original SEM" />
            </div>
          ) : (
            <div className="image-placeholder" style={{ height: 240 }}>
              <span className="material-symbols-rounded" style={{ fontSize: 28, color: "var(--muted)" }}>image</span>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">local_fire_department</span>
            GRADCAM HEATMAP · CONVOLUTIONAL ATTENTION
          </div>
          {hasData ? (
            showOverlay ? (
              <div className="overlay-container">
                <img src={inspection.input_image} alt="Original" />
                <img src={inspection.heatmap_image} alt="Grad-CAM" className="overlay-heatmap" style={{ opacity }} />
              </div>
            ) : (
              <div className="image-frame">
                <img src={inspection.heatmap_image} alt="Grad-CAM heatmap" />
              </div>
            )
          ) : (
            <div className="image-placeholder" style={{ height: 240 }}>
              <span className="material-symbols-rounded" style={{ fontSize: 28, color: "var(--muted)" }}>local_fire_department</span>
            </div>
          )}

          <div className="heatmap-legend" style={{ marginTop: 12 }}>
            <div className="heatmap-legend-label">LOW</div>
            <div className="heatmap-legend-bar" />
            <div className="heatmap-legend-label">HIGH</div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            {["COOL", "MODERATE", "WARM", "CRITICAL"].map((label) => (
              <div key={label} style={{ fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--muted)", letterSpacing: "0.06em" }}>{label}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="card" style={{ borderLeft: "3px solid var(--accent)" }}>
        <div className="card-title" style={{ marginBottom: 16 }}>
          <span className="material-symbols-rounded">psychology</span>
          EXPLAINABILITY ANALYSIS
        </div>

        {!explainability ? (
          <div style={{ fontSize: 13, color: "var(--muted)", fontStyle: "italic", padding: "12px 0" }}>
            // No automated reasoning available for this inspection yet.
          </div>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, gap: 12 }}>
              <div style={{ fontSize: 13, color: "var(--secondary)", lineHeight: 1.7, flex: 1 }}>
                {explainability.summary}
              </div>
              {explainability.certainty && (
                <span className={`chip ${explainability.certainty === "high" ? "success" : explainability.certainty === "low" ? "warn" : "info"}`} style={{ textTransform: "capitalize", flexShrink: 0 }}>
                  {explainability.certainty} confidence
                </span>
              )}
            </div>

            <div style={{ maxHeight: 560, overflowY: "auto", paddingRight: 6 }}>
              <ExplainabilityBlock title="Prediction Reasoning" icon="analytics" section={predictionReasoning} />
              <ExplainabilityBlock title="Heatmap Interpretation" icon="local_fire_department" section={heatmapInterpretation} />
              <ExplainabilityBlock title="Defect Pattern Context" icon="library_books" section={defectPatternContext} />
              <ExplainabilityBlock title="Confidence Analysis" icon="verified" section={confidenceAnalysis} />
              <ExplainabilityBlock title="Drift Impact" icon="monitor_heart" section={driftImpact} />
              <ExplainabilityBlock title="Engineering Interpretation" icon="precision_manufacturing" section={engineeringInterpretation} />
              <ExplainabilityBlock
                title="Recommended Investigation Steps"
                icon="checklist"
                section={{ steps: recommendedSteps }}
                numbered
              />
            </div>

            {explainability.rag_sources?.length > 0 && (
              <div style={{ marginTop: 16, borderTop: "1px solid var(--stroke)", paddingTop: 12, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span className="material-symbols-rounded" style={{ fontSize: 14, color: "var(--muted)" }}>library_books</span>
                <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Sources:</span>
                {explainability.rag_sources.map((src, index) => (
                  <span key={index} style={{ fontSize: 11, color: "var(--secondary)", background: "var(--bg-1)", padding: "2px 6px", borderRadius: 4, border: "1px solid var(--stroke)" }}>
                    {src.replace(".txt", "")}
                  </span>
                ))}
              </div>
            )}

            {explainability.fallback_used && (
              <div style={{ marginTop: 12, fontSize: 10, color: "var(--accent-warn)", textAlign: "right" }}>
                * Fallback reasoning active
              </div>
            )}
          </>
        )}
      </div>

      <div className="grid-2">
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 13 }}>verified</span>
            MODEL FIDELITY
          </div>
          {hasData ? (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span className="stat-foot">Confidence Score</span>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 14 }}>{confidence}%</span>
              </div>
              <div className="progress thick">
                <span style={{ width: `${confidence}%` }} />
              </div>
              <div style={{ display: "grid", gap: 6, marginTop: 10 }}>
                {(confidenceAnalysis.bullets ?? []).slice(0, 3).map((item, index) => (
                  <div key={index} className="stat-foot">{item}</div>
                ))}
                {(confidenceAnalysis.explanation ?? []).slice(0, 2).map((item, index) => (
                  <div key={`exp-${index}`} className="stat-foot">{item}</div>
                ))}
              </div>
            </div>
          ) : (
            <div className="reasoning-panel-body">No data available.</div>
          )}
        </div>

        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 13 }}>my_location</span>
            REGION OF INTEREST
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {(heatmapInterpretation.bullets ?? []).slice(0, 4).map((item, index) => (
              <div key={index} className="reasoning-panel-body">{item}</div>
            ))}
            {(heatmapInterpretation.explanation ?? []).slice(0, 2).map((item, index) => (
              <div key={`heat-${index}`} className="reasoning-panel-body">{item}</div>
            ))}
          </div>
          {hasData && (
            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span className={`chip ${inspection.triage?.priority === "high" ? "warn" : "info"}`}>
                PRIORITY: {inspection.triage?.priority ?? "NORMAL"}
              </span>
              <span className="chip info">
                REGION: {heatmapAnalysis.dominant_region ?? "N/A"}
              </span>
            </div>
          )}
        </div>
      </div>

      {hasData && inspection.synthetic_images?.length > 0 && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">auto_awesome_mosaic</span>
            SYNTHETIC AUGMENTATIONS GENERATED ({inspection.synthetic_images.length})
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(80px, 1fr))", gap: 10 }}>
            {inspection.synthetic_images.map((src, i) => (
              <div className="image-frame" key={i}>
                <img src={src} alt={`synthetic-${i}`} />
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
