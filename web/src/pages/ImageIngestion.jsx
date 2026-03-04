import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useInspection } from "../context/InspectionContext.jsx";

export default function ImageIngestion() {
  const [file, setFile] = useState(null);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.45);
  const [synthTriggerMode, setSynthTriggerMode] = useState("above");
  const [maxLowConfidence, setMaxLowConfidence] = useState(1);
  const [synthCount, setSynthCount] = useState(10);
  const [autoRetrain, setAutoRetrain] = useState(false);
  const [retrainEpochs, setRetrainEpochs] = useState(1);
  const navigate = useNavigate();
  const { runAnalysis, loading, error } = useInspection();

  const handleAnalyze = async () => {
    if (!file) {
      return;
    }
    try {
      await runAnalysis(file, {
        confidenceThreshold,
        synthTriggerMode,
        maxLowConfidence,
        synthCount,
        synthSize: 64,
        autoRetrain,
        retrainEpochs,
        minAccuracyDelta: 0.0
      });
      navigate("/defect-detection");
    } catch (err) {
      // error handled in context
    }
  };

  return (
    <>
      <div>
        <div className="topbar-title">Image Ingestion</div>
        <div className="stat-foot">Upload wafer images for inspection</div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h3>Image Upload</h3>
          <div className="upload-panel">
            <div className="upload-icon">{"\u2191"}</div>
            <div style={{ fontWeight: 600 }}>Drop wafer image here</div>
            <div className="stat-foot">or click to browse</div>
            <div className="stat-foot">Supports: JPEG, PNG - Max 10MB</div>
            <input
              type="file"
              accept="image/png, image/jpeg"
              style={{ marginTop: 12 }}
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
              <label className="stat-foot">
                Confidence Threshold
                <input
                  type="number"
                  min="0.1"
                  max="0.95"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={(event) => setConfidenceThreshold(Number(event.target.value))}
                  style={{ marginLeft: 8, width: 80 }}
                />
              </label>
              <label className="stat-foot">
                Synthetic Trigger Mode
                <select
                  value={synthTriggerMode}
                  onChange={(event) => setSynthTriggerMode(event.target.value)}
                  style={{ marginLeft: 8 }}
                >
                  <option value="above">Above Threshold</option>
                  <option value="below">Below Threshold</option>
                </select>
              </label>
              <label className="stat-foot">
                Consecutive Trigger Count
                <input
                  type="number"
                  min="1"
                  max="5"
                  step="1"
                  value={maxLowConfidence}
                  onChange={(event) => setMaxLowConfidence(Number(event.target.value))}
                  style={{ marginLeft: 8, width: 60 }}
                />
              </label>
              <label className="stat-foot">
                Synthetic Images
                <input
                  type="number"
                  min="2"
                  max="24"
                  step="2"
                  value={synthCount}
                  onChange={(event) => setSynthCount(Number(event.target.value))}
                  style={{ marginLeft: 8, width: 60 }}
                />
              </label>
              <label className="stat-foot">
                Auto Retrain
                <input
                  type="checkbox"
                  checked={autoRetrain}
                  onChange={(event) => setAutoRetrain(event.target.checked)}
                  style={{ marginLeft: 8 }}
                />
              </label>
              <label className="stat-foot">
                Retrain Epochs
                <input
                  type="number"
                  min="1"
                  max="5"
                  step="1"
                  value={retrainEpochs}
                  onChange={(event) => setRetrainEpochs(Number(event.target.value))}
                  style={{ marginLeft: 8, width: 60 }}
                />
              </label>
            </div>
            <div style={{ marginTop: 12 }}>
              <button className="button primary" onClick={handleAnalyze} disabled={loading || !file}>
                {loading ? "Analyzing..." : "Run Analysis"}
              </button>
              {error ? <div className="note" style={{ marginTop: 8 }}>{error}</div> : null}
            </div>
          </div>
        </div>
        <div className="card">
          <h3>Demo Images</h3>
          <div className="grid-2">
            <div className="card">
              <div className="wafer mini-grid">Sample</div>
              <div style={{ marginTop: 10, fontWeight: 600 }}>Scratch Defect</div>
              <div className="stat-foot">Linear surface damage</div>
            </div>
            <div className="card">
              <div className="wafer mini-grid">Sample</div>
              <div style={{ marginTop: 10, fontWeight: 600 }}>Particle Contamination</div>
              <div className="stat-foot">Foreign material deposit</div>
            </div>
            <div className="card">
              <div className="wafer mini-grid">Sample</div>
              <div style={{ marginTop: 10, fontWeight: 600 }}>Pattern Defect</div>
              <div className="stat-foot">Non-uniform etch</div>
            </div>
            <div className="card">
              <div className="wafer mini-grid">Sample</div>
              <div style={{ marginTop: 10, fontWeight: 600 }}>Normal</div>
              <div className="stat-foot">No defect detected</div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
