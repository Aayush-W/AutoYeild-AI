import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useInspection } from "../context/InspectionContext.jsx";

const DEFECT_PROFILES = [
  {
    color: "yellow",
    name: "Linear Defect",
    desc: "Caused by mechanical contact during transport. High yield impact if crossing active areas.",
  },
  {
    color: "red",
    name: "Contamination",
    desc: "Aerosolized debris or chemical residue. Common in low-filter environments.",
  },
  {
    color: "blue",
    name: "Process Deviation",
    desc: "CVD inconsistency at the wafer perimeter.",
  },
  {
    color: "purple",
    name: "Random Failure",
    desc: "Point failures linked to lithography mask errors or photolithographic anomalies.",
  },
];

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

  /* ── Drag & Drop ── */
  const onDragOver = useCallback((e) => { e.preventDefault(); setDragging(true); }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);
  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleAnalyze = async () => {
    if (!file) return;
    try {
      await runAnalysis(file, {
        confidenceThreshold,
        synthTriggerMode,
        maxLowConfidence,
        synthCount,
        synthSize: 64,
        autoRetrain,
        retrainEpochs,
        minAccuracyDelta: 0.0,
      });
      navigate("/defect-detection");
    } catch {
      /* error surfaced via context */
    }
  };

  /* ── Toggle component ── */
  const Toggle = ({ checked, onChange }) => (
    <label className="toggle-switch">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track" />
    </label>
  );

  return (
    <>
      {/* Section header */}
      <div className="section-header">
        <div>
          <div className="section-title">Ingestion Console</div>
          <div className="section-sub">
            Import raw wafer scans for high-precision defect classification.
          </div>
        </div>
        <div className="live-badge">Standby</div>
      </div>

      <div className="grid-2">
        {/* ── Left column: Upload + Parameters ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Upload Zone */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>
              <span className="material-symbols-rounded">upload_file</span>
              Ready for Upload
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
                  <div className="upload-zone-title" style={{ color: "var(--accent-2)" }}>
                    {file.name}
                  </div>
                  <div className="upload-zone-sub">
                    {(file.size / 1024).toFixed(1)} KB — ready for analysis
                  </div>
                </>
              ) : (
                <>
                  <div className="upload-zone-title">Drop wafer scan here</div>
                  <div className="upload-zone-sub">
                    Drag &amp; drop high-resolution .TIFF or .PNG directly
                  </div>
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

            <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
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
            {error && <div className="error-note" style={{ marginTop: 8 }}>{error}</div>}
          </div>

          {/* Engine Parameters */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>
              <span className="material-symbols-rounded">tune</span>
              Engine Parameters
            </div>

            <div className="param-panel">
              <div className="param-row">
                <div className="param-label">Confidence Threshold</div>
                <input
                  type="number"
                  min="0.1" max="0.95" step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">Synth Trigger Mode</div>
                <select
                  value={synthTriggerMode}
                  onChange={(e) => setSynthTriggerMode(e.target.value)}
                  className="param-select"
                >
                  <option value="above">Above Threshold</option>
                  <option value="below">Below Threshold</option>
                </select>
              </div>
              <div className="param-row">
                <div className="param-label">Consecutive Triggers</div>
                <input
                  type="number"
                  min="1" max="5" step="1"
                  value={maxLowConfidence}
                  onChange={(e) => setMaxLowConfidence(Number(e.target.value))}
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">Synthetic Images</div>
                <input
                  type="number"
                  min="2" max="24" step="2"
                  value={synthCount}
                  onChange={(e) => setSynthCount(Number(e.target.value))}
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">Auto Retrain</div>
                <div className="toggle-wrap">
                  <Toggle checked={autoRetrain} onChange={setAutoRetrain} />
                  <span className="stat-foot">{autoRetrain ? "Enabled" : "Disabled"}</span>
                </div>
              </div>
              {autoRetrain && (
                <div className="param-row">
                  <div className="param-label">Retrain Epochs</div>
                  <input
                    type="number"
                    min="1" max="5" step="1"
                    value={retrainEpochs}
                    onChange={(e) => setRetrainEpochs(Number(e.target.value))}
                    className="param-input"
                  />
                </div>
              )}
            </div>

            {/* Advisory */}
            <div className="advisory-banner" style={{ marginTop: 14 }}>
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
                <><span>Analyzing</span> — pipeline in progress…</>
              ) : (
                <>Ingestion Queue — <span>Standby mode</span>: Listening for data stream…</>
              )}
            </div>
          </div>
        </div>

        {/* ── Right column: Defect Profiles ── */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">category</span>
            Sample Defect Profiles
          </div>
          <div className="defect-profile">
            {DEFECT_PROFILES.map((dp) => (
              <div className="defect-profile-card" key={dp.name}>
                <div className={`defect-dot ${dp.color === "red" ? "red" : dp.color === "blue" ? "blue" : dp.color === "purple" ? "purple" : ""}`} />
                <div>
                  <div className="defect-name">{dp.name}</div>
                  <div className="defect-desc">{dp.desc}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Tips */}
          <div
            style={{
              marginTop: 20,
              padding: "14px 16px",
              background: "rgba(7,14,26,0.8)",
              borderRadius: "var(--r-md)",
              border: "1px solid var(--stroke)",
            }}
          >
            <div
              className="card-title"
              style={{ marginBottom: 10 }}
            >
              <span className="material-symbols-rounded">lightbulb</span>
              Tips
            </div>
            <ul style={{ color: "var(--muted)", fontSize: 11, lineHeight: 1.7, paddingLeft: 14 }}>
              <li>Use 512×512 or larger images for best accuracy.</li>
              <li>TIFF format preserves full bit-depth for SEM scans.</li>
              <li>Enable Auto Retrain only when drift is frequent.</li>
              <li>Reduce threshold if results seem over-confident.</li>
            </ul>
          </div>
        </div>
      </div>
    </>
  );
}
