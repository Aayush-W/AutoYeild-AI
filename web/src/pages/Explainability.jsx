import { useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

// All existing logic PRESERVED
export default function Explainability() {
  const { inspection } = useInspection();
  const navigate = useNavigate();
  const hasData = Boolean(inspection);
  const [showOverlay, setShowOverlay] = useState(true);
  const [sideBySide, setSideBySide] = useState(true);
  const [opacity, setOpacity] = useState(0.7);

  const confidence = hasData ? Math.round(inspection.confidence * 100) : null;
  const reasoning = inspection?.reasoning ?? {};

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
      {/* Section Header */}
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

      {/* Top row: Active Model Status + Feature Drift */}
      <div className="grid-2">
        {/* Active Model Status */}
        <div className="model-status-widget" style={{ flexDirection: "column", alignItems: "flex-start", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
            <div className="engine-status-dot" />
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Active Model Status</div>
          </div>
          <div className="model-status-name">DefectNet-v4.2-TRT</div>
          <div style={{ display: "flex", gap: 12 }}>
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Target Layer</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", marginTop: 2 }}>M2_Cu</div>
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Lot ID</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", marginTop: 2 }}>L-9921</div>
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Process Tool</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", marginTop: 2 }}>Litho-04</div>
            </div>
          </div>
          <div className="model-status-badge">ACTIVE</div>
        </div>

        {/* Feature Drift Monitor */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">monitor_heart</span>
              FEATURE DRIFT MONITOR
            </div>
            <span className="chip warn">WATCH</span>
          </div>
          {/* Mini drift chart */}
          <div style={{ height: 80, display: "flex", alignItems: "flex-end", gap: 3 }}>
            {[30, 42, 38, 55, 48, 60, 72, 65, 80, 74, 88, 78, 85, 92, 78, 68, 74, 80, 76, 72, 68, 85, 90, 95].map((v, i) => (
              <div key={i} style={{
                flex: 1,
                height: `${v}%`,
                background: v > 80 ? "var(--accent)" : v > 60 ? "var(--accent-warn)" : "rgba(0,0,0,0.12)",
                borderRadius: 0,
                transition: "background 0.2s",
              }} title={`${v}%`} />
            ))}
          </div>
          <div className="stat-foot" style={{ marginTop: 8 }}>
            // Focus drift score over last 24 exposures · Litho-04
          </div>
        </div>
      </div>

      {/* Visualization Controls */}
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

      {/* AI Attention Map & Heatmap panels */}
      <div className={sideBySide ? "grid-2" : ""}>
        {/* Original SEM */}
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

        {/* GradCAM Heatmap */}
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

          {/* Heatmap Legend */}
          <div className="heatmap-legend" style={{ marginTop: 12 }}>
            <div className="heatmap-legend-label">LOW</div>
            <div className="heatmap-legend-bar" />
            <div className="heatmap-legend-label">HIGH</div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            {["COOL", "MODERATE", "WARM", "CRITICAL"].map(l => (
              <div key={l} style={{ fontFamily: "var(--font-mono)", fontSize: 8, color: "var(--muted)", letterSpacing: "0.06em" }}>{l}</div>
            ))}
          </div>
        </div>
      </div>

      {/* AI Insight Engine */}
      <div className="card" style={{ borderLeft: "3px solid var(--accent)" }}>
        <div className="card-title" style={{ marginBottom: 16 }}>
          <span className="material-symbols-rounded">psychology</span>
          AI INSIGHT ENGINE
        </div>
        <div style={{ fontSize: 14, color: "var(--secondary)", lineHeight: 1.7, marginBottom: 16, fontStyle: "italic" }}>
          {reasoning.cause_summary ??
            "The GradCAM attention map strongly highlights the space between two adjacent metal lines. The high-intensity activation (red) correlates with visual evidence of incomplete etching or photoresist residue. Based on historical patterns for Layer M2_Cu in Lot L-9921, this bridging defect is highly likely associated with Process Tool Litho-04 experiencing focus drift during the exposure step."}
        </div>

        <div className="card-title" style={{ marginBottom: 10, marginTop: 8 }}>
          <span className="material-symbols-rounded">build</span>
          RECOMMENDED ACTIONS
        </div>

        {[
          { icon: "build", text: "Initiate CD-SEM measurement on adjacent wafers in Lot L-9921 to confirm line-space dimensions." },
          { icon: "stop_circle", text: "Place Process Tool Litho-04 on HOLD pending focus calibration check." },
          { icon: "history", text: "Review optical emission spectroscopy (OES) logs for the Etch chamber during this run." },
        ].map((action, i) => (
          <div className="insight-action" key={i}>
            <span className="material-symbols-rounded">{action.icon}</span>
            <div className="insight-action-text">{action.text}</div>
          </div>
        ))}

        {/* Additional reasoning data if available */}
        {reasoning.reasoning_steps && (
          <div style={{ marginTop: 16, padding: "12px 14px", background: "var(--bg-1)", border: "1px solid var(--stroke)" }}>
            <div className="card-title" style={{ marginBottom: 8 }}>
              <span className="material-symbols-rounded">list</span>
              NEURAL RATIONALE
            </div>
            <div style={{ fontSize: 12, color: "var(--secondary)", lineHeight: 1.7, fontFamily: "var(--font-mono)" }}>
              {reasoning.reasoning_steps.join(" ")}
            </div>
          </div>
        )}
      </div>

      {/* Model Fidelity + Triage */}
      <div className="grid-2">
        {/* Model Fidelity */}
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
              <div className="stat-foot" style={{ marginTop: 10 }}>
                {confidence >= 90
                  ? "// High-fidelity match — strong class alignment"
                  : confidence >= 70
                    ? "// Moderate fidelity — secondary class candidates present"
                    : "// Low fidelity — consider retraining or manual review"}
              </div>
            </div>
          ) : (
            <div className="reasoning-panel-body">No data available.</div>
          )}
        </div>

        {/* Region of Interest */}
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 13 }}>my_location</span>
            REGION OF INTEREST
          </div>
          <div className="reasoning-panel-body">
            {reasoning.cause_summary ?? (
              hasData
                ? "The attention mechanism is focused on high-activation regions corresponding to the detected defect pattern."
                : "// Run an analysis to see the spatial attention region."
            )}
          </div>
          {hasData && inspection.triage && (
            <div style={{ marginTop: 12 }}>
              <span className={`chip ${inspection.triage.priority === "high" ? "warn" : "info"}`}>
                PRIORITY: {inspection.triage.priority ?? "NORMAL"}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Synthetic images (if drift triggered) — PRESERVED */}
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
