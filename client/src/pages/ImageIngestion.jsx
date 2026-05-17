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
  const {
    runAnalysis,
    loading,
    error,
    impactInputs,
    updateImpactInputs,
    impactSources,
  } = useInspection();

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

  const hasEnergyOverride = impactInputs.manualEnergyIntensityOverrideKwhPerWafer !== "";
  const hasGridOverride = impactInputs.manualGridFactorOverrideKgco2PerKwh !== "";

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
      {/* Sample Image Previews */}
      <div className="section-rule" style={{ marginTop: "16px", marginBottom: "24px" }}>
        <div className="section-rule-line" />
        <div className="section-rule-text">// ACCEPTABLE WAFER FORMATS (DATASET SAMPLES)</div>
        <div className="section-rule-line" />
      </div>

      <div style={{ display: "flex", gap: "16px", marginBottom: "32px", overflowX: "auto" }}>
        {[
          { src: "/samples/sample_center.jpg", name: "Center Defect", type: "SEM Scan (26x26)" },
          { src: "/samples/sample_edgering.jpg", name: "Edge Ring", type: "SEM Scan (26x26)" },
          { src: "/samples/sample_scratch.jpg", name: "Surface Scratch", type: "SEM Scan (26x26)" },
          { src: "/samples/sample_clean.jpg", name: "Clean Wafer", type: "SEM Scan (26x26)" }
        ].map((img, i) => (
          <div key={i} style={{ flex: 1, minWidth: "150px", background: "var(--bg-1)", border: "1px solid var(--stroke-major)", padding: "12px", borderRadius: "8px" }}>
            <img src={img.src} alt={img.name} style={{ width: "100%", height: "140px", objectFit: "contain", background: "#000", borderRadius: "4px", marginBottom: "12px", border: "1px solid var(--stroke-dim)" }} />
            <div style={{ fontSize: "13px", color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>{img.name}</div>
            <div style={{ fontSize: "11px", color: "var(--secondary)", marginTop: "4px" }}>{img.type}</div>
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

          <div className="card">
            <div className="card-title" style={{ marginBottom: 16 }}>
              <span className="material-symbols-rounded">eco</span>
              IMPACT ASSUMPTIONS
            </div>

            <div className="impact-input-grid">
              <div className="param-row">
                <div className="param-label">batch_id</div>
                <input
                  type="text"
                  value={impactInputs.batchId}
                  onChange={(e) => updateImpactInputs({ batchId: e.target.value })}
                  className="param-input"
                  placeholder="Optional batch label"
                />
              </div>
              <div className="param-row">
                <div className="param-label">batch_wafer_count</div>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={impactInputs.batchWaferCount}
                  onChange={(e) =>
                    updateImpactInputs({ batchWaferCount: Number(e.target.value) || 1 })
                  }
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">affected_wafers</div>
                <input
                  type="number"
                  min="0"
                  max={impactInputs.batchWaferCount}
                  step="1"
                  value={impactInputs.affectedWafersDetected}
                  onChange={(e) =>
                    updateImpactInputs({
                      affectedWafersDetected: Math.min(
                        impactInputs.batchWaferCount,
                        Math.max(0, Number(e.target.value) || 0)
                      ),
                    })
                  }
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">recovery_rate_pct</div>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={impactInputs.treatmentRecoveryRatePct}
                  onChange={(e) =>
                    updateImpactInputs({
                      treatmentRecoveryRatePct: Math.min(
                        100,
                        Math.max(0, Number(e.target.value) || 0)
                      ),
                    })
                  }
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">wafer_diameter_mm</div>
                <select
                  value={impactInputs.waferDiameterMm}
                  onChange={(e) =>
                    updateImpactInputs({ waferDiameterMm: Number(e.target.value) })
                  }
                  className="param-select"
                >
                  <option value="200">200mm</option>
                  <option value="300">300mm</option>
                </select>
              </div>
              <div className="param-row">
                <div className="param-label">cost_per_wafer_inr</div>
                <input
                  type="number"
                  min="0"
                  step="1000"
                  value={impactInputs.loadedCostPerWaferInr}
                  onChange={(e) =>
                    updateImpactInputs({ loadedCostPerWaferInr: Number(e.target.value) || 0 })
                  }
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">tariff_inr_per_kwh</div>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={impactInputs.electricityTariffInrPerKwh}
                  onChange={(e) =>
                    updateImpactInputs({
                      electricityTariffInrPerKwh: Number(e.target.value) || 0,
                    })
                  }
                  className="param-input"
                />
              </div>
              <div className="param-row">
                <div className="param-label">energy_override</div>
                <input
                  type="number"
                  min="0"
                  step="10"
                  value={impactInputs.manualEnergyIntensityOverrideKwhPerWafer}
                  onChange={(e) =>
                    updateImpactInputs({
                      manualEnergyIntensityOverrideKwhPerWafer: e.target.value,
                    })
                  }
                  className="param-input"
                  placeholder="Optional kWh/wafer"
                />
              </div>
              <div className="param-row">
                <div className="param-label">grid_override</div>
                <input
                  type="number"
                  min="0"
                  step="0.001"
                  value={impactInputs.manualGridFactorOverrideKgco2PerKwh}
                  onChange={(e) =>
                    updateImpactInputs({
                      manualGridFactorOverrideKgco2PerKwh: e.target.value,
                    })
                  }
                  className="param-input"
                  placeholder="Optional kgCO2e/kWh"
                />
              </div>
            </div>

            <div className="impact-source-note">
              <div className="impact-source-note-title">Source-backed defaults</div>
              <div className="impact-source-note-body">
                Energy factor: {impactSources.energyProfile.energyKwhPerCm2.toFixed(3)} kWh/cm2
                {" · "}
                Grid factor: {impactSources.gridProfile.factorValueKgco2PerKwh.toFixed(3)} kgCO2e/kWh
              </div>
              <div className="impact-source-note-body">
                Overrides: energy {hasEnergyOverride ? "ENABLED" : "OFF"} {" · "}
                grid {hasGridOverride ? "ENABLED" : "OFF"}
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
