import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useInspection } from "../context/InspectionContext.jsx";

const DEFECT_PROFILES = [
  { color: "yellow", name: "Linear Defect", desc: "Caused by mechanical contact during transport. High yield impact if crossing active areas." },
  { color: "red", name: "Contamination", desc: "Aerosolized debris or chemical residue. Common in low-filter environments." },
  { color: "blue", name: "Process Deviation", desc: "CVD inconsistency at the wafer perimeter." },
  { color: "purple", name: "Random Failure", desc: "Point failures linked to lithography mask errors or photolithographic anomalies." },
];

// All business logic PRESERVED
export default function ImageIngestion() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.45);
  const [synthTriggerMode, setSynthTriggerMode] = useState("above");
  const [maxLowConfidence, setMaxLowConfidence] = useState(1);
  const [synthCount, setSynthCount] = useState(10);
  const [autoRetrain, setAutoRetrain] = useState(false);
  const [retrainEpochs, setRetrainEpochs] = useState(1);

  const navigate = useNavigate();
  const { runAnalysis, loading, error } = useInspection();

  const onDragOver = useCallback((e) => { e.preventDefault(); setDragging(true); }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);
  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleAnalyze = async () => {
    if (!file) return;
    try {
      await runAnalysis(file, {
        confidenceThreshold, synthTriggerMode, maxLowConfidence,
        synthCount, synthSize: 64, autoRetrain, retrainEpochs, minAccuracyDelta: 0.0,
      });
      navigate("/defect-detection");
    } catch { /* error surfaced via context */ }
  };

  const Toggle = ({ checked, onChange }) => (
    <label className="toggle-switch">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track" />
    </label>
  );

  return (
    <>
      {/* Section Header */}
      <div className="section-header">
        <div>
          <div className="section-title">Ingestion Console</div>
          <div className="section-sub">
            // Import raw wafer scans for high-precision defect classification · Support: .tiff .png .raw (Max 500MB)
          </div>
        </div>
        <div className="live-badge">Standby</div>
      </div>

      {/* Batch file list preview (simulated) */}
      <div className="batch-file-list">
        {[
          { name: file?.name ?? "WFR-2023-A4-001.tiff", status: file ? "waiting" : "waiting" },
          { name: "WFR-2023-A4-002.tiff", status: "waiting" },
          { name: "WFR-2023-A4-003.tiff", status: "waiting" },
        ].map((f, i) => (
          <div className="batch-file-item" key={i}>
            <div className="batch-file-icon">
              <span className="material-symbols-rounded" style={{ fontSize: 13 }}>image</span>
            </div>
            <div className="batch-file-name">{f.name}</div>
            <div className={`batch-file-status ${i === 0 && loading ? "processing" : f.status}`}>
              {i === 0 && loading ? "PROCESSING..." : "WAITING"}
            </div>
          </div>
        ))}
      </div>

      <div className="section-rule">
        <div className="section-rule-line" />
        <div className="section-rule-text">// BATCH_INGESTION</div>
        <div className="section-rule-line" />
      </div>

      <div className="grid-2">
        {/* ── Left: Upload + Parameters ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Upload Zone */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 16 }}>
              <span className="material-symbols-rounded">upload_file</span>
              DRAG &amp; DROP WAFER IMAGES
            </div>

            <div
              className={`upload-zone${dragging ? " dragging" : ""}`}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={() => document.getElementById("wafer-file-input").click()}
            >
              <div className="upload-zone-icon">
                <span className="material-symbols-rounded">cloud_upload</span>
              </div>
              {file ? (
                <>
                  <div className="upload-zone-title" style={{ color: "var(--accent)" }}>{file.name}</div>
                  <div className="upload-zone-sub">{(file.size / 1024).toFixed(1)} KB — ready for analysis</div>
                </>
              ) : (
                <>
                  <div className="upload-zone-title">Drop wafer scan here</div>
                  <div className="upload-zone-sub">Support: .tiff, .png, .raw (Max 500MB)</div>
                  <div className="upload-zone-sub">or click to browse files</div>
                </>
              )}
              <input
                id="wafer-file-input"
                type="file"
                accept="image/png,image/jpeg,image/tiff"
                style={{ display: "none" }}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </div>

            <div style={{ marginTop: 16, display: "flex", gap: 10 }}>
              <button
                className="btn primary"
                onClick={handleAnalyze}
                disabled={loading || !file}
                style={{ flex: 1 }}
              >
                <span className="material-symbols-rounded" style={{ fontSize: 15 }}>
                  {loading ? "hourglass_bottom" : "play_arrow"}
                </span>
                {loading ? "Analyzing…" : "Run Analysis"}
              </button>
              {file && (
                <button className="btn" onClick={() => setFile(null)}>
                  <span className="material-symbols-rounded" style={{ fontSize: 15 }}>close</span>
                </button>
              )}
            </div>
            {error && <div className="error-note" style={{ marginTop: 10 }}>{error}</div>}
          </div>

          {/* Engine Parameters */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 16 }}>
              <span className="material-symbols-rounded">tune</span>
              ENGINE PARAMETERS
            </div>

            <div className="param-panel">
              <div className="param-row">
                <div className="param-label">confidence_threshold</div>
                <input type="number" min="0.1" max="0.95" step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                  className="param-input" />
              </div>
              <div className="param-row">
                <div className="param-label">synth_trigger_mode</div>
                <select value={synthTriggerMode}
                  onChange={(e) => setSynthTriggerMode(e.target.value)}
                  className="param-select">
                  <option value="above">above_threshold</option>
                  <option value="below">below_threshold</option>
                </select>
              </div>
              <div className="param-row">
                <div className="param-label">consecutive_triggers</div>
                <input type="number" min="1" max="5" step="1"
                  value={maxLowConfidence}
                  onChange={(e) => setMaxLowConfidence(Number(e.target.value))}
                  className="param-input" />
              </div>
              <div className="param-row">
                <div className="param-label">synthetic_images</div>
                <input type="number" min="2" max="24" step="2"
                  value={synthCount}
                  onChange={(e) => setSynthCount(Number(e.target.value))}
                  className="param-input" />
              </div>
              <div className="param-row">
                <div className="param-label">auto_retrain</div>
                <div className="toggle-wrap">
                  <Toggle checked={autoRetrain} onChange={setAutoRetrain} />
                  <span className="stat-foot">{autoRetrain ? "ENABLED" : "DISABLED"}</span>
                </div>
              </div>
              {autoRetrain && (
                <div className="param-row">
                  <div className="param-label">retrain_epochs</div>
                  <input type="number" min="1" max="5" step="1"
                    value={retrainEpochs}
                    onChange={(e) => setRetrainEpochs(Number(e.target.value))}
                    className="param-input" />
                </div>
              )}
            </div>

            <div className="advisory-banner" style={{ marginTop: 16 }}>
              <span className="material-symbols-rounded">info</span>
              <div>
                <div className="advisory-label">System Advisory</div>
                <div className="advisory-text">
                  Current engine optimized for 12nm process node. Ensure lighting
                  calibration matches Standard-B prior to mass ingestion.
                </div>
              </div>
            </div>
          </div>

          {/* Queue Status */}
          <div className={`queue-status${loading ? " active" : ""}`}>
            <span className="material-symbols-rounded">
              {loading ? "sync" : "radio_button_checked"}
            </span>
            <div className="queue-text">
              {loading ? (
                <><span>Analyzing</span> — inference pipeline active…</>
              ) : (
                <>Ingestion Queue — <span>Standby mode</span>: Listening for data stream…</>
              )}
            </div>
          </div>
        </div>

        {/* ── Right: Defect Profiles ── */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>
            <span className="material-symbols-rounded">category</span>
            SAMPLE DEFECT PROFILES
          </div>
          <div className="defect-profile">
            {DEFECT_PROFILES.map((dp) => (
              <div className="defect-profile-card" key={dp.name}>
                <div className={`defect-dot ${dp.color === "red" ? "red" : dp.color === "blue" ? "blue" : dp.color === "purple" ? "purple" : "yellow"}`} />
                <div>
                  <div className="defect-name">{dp.name}</div>
                  <div className="defect-desc">{dp.desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 24, padding: "16px", background: "var(--bg-1)", border: "1px solid var(--stroke-major)" }}>
            <div className="card-title" style={{ marginBottom: 12 }}>
              <span className="material-symbols-rounded">lightbulb</span>
              ENGINEERING TIPS
            </div>
            <ul style={{ color: "var(--secondary)", fontSize: 12, lineHeight: 1.8, paddingLeft: 16, fontFamily: "var(--font-mono)" }}>
              <li>// Use 512×512 or larger images for best accuracy.</li>
              <li>// TIFF format preserves full bit-depth for SEM scans.</li>
              <li>// Enable Auto Retrain only when drift is frequent.</li>
              <li>// Reduce threshold if results seem over-confident.</li>
            </ul>
          </div>
        </div>
      </div>
    </>
  );
}
