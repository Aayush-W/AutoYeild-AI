import { useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

export default function Explainability() {
  const { inspection } = useInspection();
  const navigate = useNavigate();
  const hasData = Boolean(inspection);
  const [showOverlay, setShowOverlay] = useState(true);
  const [sideBySide, setSideBySide] = useState(true);
  const [opacity, setOpacity] = useState(0.7);

  const confidence = hasData ? Math.round(inspection.confidence * 100) : null;
  const reasoning = inspection?.reasoning ?? {};

  /* ── Toggle ── */
  const Toggle = ({ checked, onChange, label }) => (
    <div className="param-row" style={{ paddingBottom: 0 }}>
      <span className="param-label">{label}</span>
      <label className="toggle-switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className="toggle-track" />
      </label>
    </div>
  );

  return (
    <>
      {/* Header */}
      <div className="section-header">
        <div>
          <div className="section-title">Grad-CAM Visualization</div>
          <div className="section-sub">
            Explainability heatmap analysis — convolutional attention mapping
          </div>
        </div>
        {hasData && (
          <span className="chip info">
            {inspection.defect_class && (
              <span style={{ textTransform: "capitalize" }}>{inspection.defect_class}</span>
            )}
            &nbsp;• {confidence}% conf
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
              Run an analysis first in{" "}
              <button
                className="btn sm"
                style={{ display: "inline-flex", padding: "2px 8px" }}
                onClick={() => navigate("/ingestion")}
              >
                Image Ingestion
              </button>
              .
            </div>
          </div>
        </div>
      )}

      {/* Controls card */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 12 }}>
          <span className="material-symbols-rounded">tune</span>
          Visualization Controls
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          <Toggle checked={showOverlay} onChange={setShowOverlay} label="Show Heatmap Overlay" />
          <Toggle checked={sideBySide} onChange={setSideBySide} label="Side-by-Side Comparison" />
          <div className="param-row">
            <span className="param-label">Overlay Opacity</span>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(opacity * 100)}
                onChange={(e) => setOpacity(Number(e.target.value) / 100)}
                style={{ width: 120 }}
              />
              <span className="stat-foot">{Math.round(opacity * 100)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Image panels */}
      <div className={sideBySide ? "grid-2" : ""}>
        {/* Original SEM */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            <span className="material-symbols-rounded">image</span>
            Original SEM Scan
          </div>
          {hasData ? (
            <div className="image-frame">
              <img src={inspection.input_image} alt="Original SEM" />
            </div>
          ) : (
            <div className="image-placeholder" style={{ height: 220 }}>
              <span className="material-symbols-rounded" style={{ fontSize: 32, color: "var(--dim)" }}>
                image
              </span>
            </div>
          )}
        </div>

        {/* Grad-CAM Heatmap */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            <span className="material-symbols-rounded">local_fire_department</span>
            Grad-CAM Heatmap
          </div>
          {hasData ? (
            showOverlay ? (
              <div className="overlay-container">
                <img src={inspection.input_image} alt="Original" />
                <img
                  src={inspection.heatmap_image}
                  alt="Grad-CAM"
                  className="overlay-heatmap"
                  style={{ opacity }}
                />
              </div>
            ) : (
              <div className="image-frame">
                <img src={inspection.heatmap_image} alt="Grad-CAM heatmap" />
              </div>
            )
          ) : (
            <div className="image-placeholder" style={{ height: 220 }}>
              <span className="material-symbols-rounded" style={{ fontSize: 32, color: "var(--dim)" }}>
                local_fire_department
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Reasoning panels */}
      <div className="grid-2">
        {/* Region of Interest */}
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>my_location</span>
            Region of Interest
          </div>
          <div className="reasoning-panel-body">
            {reasoning.cause_summary ?? (
              hasData
                ? "The attention mechanism is focused on high-activation regions corresponding to the detected defect pattern."
                : "Run an analysis to see the spatial attention region."
            )}
          </div>
        </div>

        {/* Neural Rationale */}
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>psychology</span>
            Neural Rationale
          </div>
          <div className="reasoning-panel-body">
            {reasoning.reasoning_steps?.join(" ") ?? reasoning.detailed_analysis ?? (
              hasData
                ? `Convolutional filters show high activation for features aligned with historical '${inspection.defect_class}' defect profiles.`
                : "Convolutional layer activation analysis will appear here after inference."
            )}
          </div>
        </div>

        {/* Model Fidelity */}
        <div className="reasoning-panel">
          <div className="reasoning-panel-title">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>verified</span>
            Model Fidelity
          </div>
          {hasData ? (
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 8,
                }}
              >
                <span className="stat-foot">Confidence</span>
                <span style={{ fontWeight: 700, fontSize: 13 }}>{confidence}%</span>
              </div>
              <div className="progress thick">
                <span style={{ width: `${confidence}%` }} />
              </div>
              <div className="stat-foot" style={{ marginTop: 8 }}>
                {confidence >= 90
                  ? "High-fidelity match — strong class alignment"
                  : confidence >= 70
                    ? "Moderate fidelity — secondary class candidates present"
                    : "Low fidelity — consider retraining or manual review"}
              </div>
            </div>
          ) : (
            <div className="reasoning-panel-body">No data available.</div>
          )}
        </div>

        {/* Triage */}
        {hasData && inspection.triage && (
          <div className="reasoning-panel">
            <div className="reasoning-panel-title">
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>flag</span>
              Triage Assessment
            </div>
            <div className="reasoning-panel-body">
              {inspection.triage.reason ?? "Triage completed automatically."}
            </div>
            <div style={{ marginTop: 8 }}>
              <span
                className={`chip ${inspection.triage.priority === "high" ? "warn" : "info"}`}
              >
                Priority: {inspection.triage.priority ?? "normal"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Synthetic images (if drift triggered) */}
      {hasData && inspection.synthetic_images?.length > 0 && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            <span className="material-symbols-rounded">auto_awesome_mosaic</span>
            Synthetic Augmentations Generated ({inspection.synthetic_images.length})
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(80px, 1fr))",
              gap: 10,
            }}
          >
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
