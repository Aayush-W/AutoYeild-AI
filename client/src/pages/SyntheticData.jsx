import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

export default function SyntheticData() {
  const { inspection } = useInspection();
  const navigate = useNavigate();
  const images = inspection?.synthetic_images ?? [];
  const hasImages = images.length > 0;

  return (
    <>
      <div className="section-header">
        <div>
          <div className="section-title">Synthetic Data</div>
          <div className="section-sub">
            Augmented samples generated from the latest drift-triggered event
          </div>
        </div>
        {hasImages && (
          <span className="chip info">{images.length} images</span>
        )}
      </div>

      {/* Info banner */}
      <div className="advisory-banner">
        <span className="material-symbols-rounded">auto_fix_high</span>
        <div>
          <div className="advisory-label">Augmentation Engine</div>
          <div className="advisory-text">
            Synthetic images are generated via augmentation transforms (noise, rotation,
            brightness jitter) on the detected defect class when a drift event is triggered.
            These are used to supplement the retraining dataset.
          </div>
        </div>
      </div>

      {/* Synthetic image grid */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 14 }}>
          <span className="material-symbols-rounded">auto_awesome_mosaic</span>
          Latest Synthetic Batch
          {inspection && (
            <span className="stat-foot" style={{ marginLeft: 10, textTransform: "capitalize" }}>
              class: {inspection.defect_class}
            </span>
          )}
        </div>
        {hasImages ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))",
              gap: 12,
            }}
          >
            {images.map((src, idx) => (
              <div className="image-frame" key={`synth-${idx}`}>
                <img src={src} alt={`Synthetic ${idx + 1}`} />
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 12,
              padding: "32px 0",
            }}
          >
            <span
              className="material-symbols-rounded"
              style={{ fontSize: 42, color: "var(--dim)" }}
            >
              auto_awesome_mosaic
            </span>
            <div className="stat-foot">No synthetic images generated yet.</div>
            <div className="stat-foot" style={{ maxWidth: 320, textAlign: "center" }}>
              Run an analysis with a confidence that triggers drift (based on your threshold
              settings) to automatically generate synthetic augmentations.
            </div>
            <button className="btn sm" onClick={() => navigate("/ingestion")}>
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>upload_file</span>
              Go to Ingestion
            </button>
          </div>
        )}
      </div>

      {/* Stats if available */}
      {hasImages && (
        <div className="grid-4">
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">photo_library</span>
              Images Generated
            </div>
            <div className="metric-value">{images.length}</div>
            <div className="metric-foot">this batch</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">category</span>
              Target Class
            </div>
            <div className="metric-value" style={{ fontSize: 18, textTransform: "capitalize" }}>
              {inspection?.defect_class ?? "—"}
            </div>
            <div className="metric-foot">drift-triggered</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">speed</span>
              Trigger Mode
            </div>
            <div className="metric-value" style={{ fontSize: 16 }}>
              {inspection?.synth_trigger_mode ?? "—"}
            </div>
            <div className="metric-foot">threshold mode</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">model_training</span>
              Auto Retrain
            </div>
            <div className="metric-value" style={{ fontSize: 16 }}>
              {inspection?.auto_retrain ? "On" : "Off"}
            </div>
            <div className="metric-foot">
              {inspection?.auto_retrain ? (
                <span className="chip">Active</span>
              ) : (
                <span className="chip info">Disabled</span>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
