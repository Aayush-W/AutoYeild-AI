import { useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";
import {
  ImpactBoard,
  ImpactSessionLedger,
  ImpactSourceCard,
} from "../components/ImpactBoard.jsx";
import { generateAnalysisReport } from "../api/client.js";
import { buildAnalysisReportPayload, downloadAnalysisReport } from "../utils/reportBuilder.js";

// All data logic PRESERVED
const DEFECT_DESCRIPTIONS = {
  scratch: "Linear mechanical damage on wafer surface.",
  particle: "Foreign material deposition causing contamination.",
  crack: "Structural fracture or stress-induced cracking.",
  clean: "No defect detected on wafer surface.",
  normal: "No defect detected on wafer surface.",
  random: "Scattered defect points across the surface.",
  local: "Localized defect cluster in a specific region.",
  edge_ring: "Ring-shaped defects near the wafer edge.",
  center: "Defects concentrated near the wafer center.",
};

const SEVERITY_CHIP = {
  "Critical": "danger",
  "High": "warn",
  "Medium": "warn",
  "Low": "info",
  "Minimal": "",
};

export default function DefectDetection() {
  const {
    inspection,
    history,
    metrics,
    impactInputs,
    impactResult,
    impactHistory,
    impactSummary,
  } = useInspection();
  const navigate = useNavigate();
  const [reportLoading, setReportLoading] = useState(false);
  const hasData = Boolean(inspection);

  const label = hasData ? inspection.defect_class : null;
  const normalKey = label?.toLowerCase().replace(/[\s-]+/g, "_").trim();
  const description = DEFECT_DESCRIPTIONS[normalKey] ?? "Defect description unavailable.";
  const severity = inspection?.reasoning?.severity_assessment ?? inspection?.severity ?? "Medium";
  const severityChip = SEVERITY_CHIP[severity] ?? "warn";
  const confidence = hasData ? Math.round(inspection.confidence * 100) : null;

  const histBatches = history.length ? [...history].reverse().slice(0, 4) : [];

  const handleDownloadReport = async () => {
    if (!inspection || reportLoading) {
      return;
    }

    setReportLoading(true);

    const reportPayload = buildAnalysisReportPayload({
      inspection,
      history,
      metrics,
      impactInputs,
      impactResult,
      impactHistory,
      impactSummary,
    });

    try {
      const detailedReport = await generateAnalysisReport(reportPayload);
      downloadAnalysisReport(detailedReport);
    } catch (err) {
      window.alert(err.message || "Failed to generate the PDF report.");
    } finally {
      setReportLoading(false);
    }
  };

  return (
    <>
      {/* Section Header */}
      <div className="section-header">
        <div>
          <div className="section-title">Defect Detection Viewer</div>
          <div className="section-sub">
            // Real-time inference and batch processing · Target model: DefectNet-v4.2-TRT
          </div>
        </div>
        {hasData && (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={handleDownloadReport}>
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>
                {reportLoading ? "hourglass_top" : "download"}
              </span>
              {reportLoading ? "Generating PDF Report..." : "Download PDF Report"}
            </button>
            <span className={`chip ${severityChip}`}>{severity}</span>
            <span className="chip info">{inspection.inference_time_ms} ms</span>
          </div>
        )}
      </div>

      {/* Engine Banner */}
      <div className="engine-banner">
        <div className="engine-banner-left">
          <div className="engine-status-dot" style={{ background: hasData ? "var(--accent-success)" : "var(--accent-warn)" }} />
          <div>
            <div className="engine-title">
              {hasData ? `Wafer ID: ${inspection.inspection_id}` : "Detection Inference"}
            </div>
            <div className="engine-subtitle">
              {hasData
                ? `// Batch #${inspection.inspection_id?.split("-")[1] ?? "—"} · ${inspection.timestamp}`
                : "// Run an analysis in Image Ingestion to see results"}
            </div>
          </div>
        </div>
        {!hasData && (
          <button className="btn" onClick={() => navigate("/ingestion")}>
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>upload_file</span>
            Go to Ingestion
          </button>
        )}
      </div>

      {!hasData && (
        <div className="alert info">
          <div className="alert-icon">
            <span className="material-symbols-rounded" style={{ color: "var(--accent-blue)", fontSize: 18 }}>info</span>
          </div>
          <div className="alert-body">
            <div className="alert-title">// No inspection data yet</div>
            <div className="alert-detail">Upload a wafer image in Image Ingestion to run a defect analysis.</div>
          </div>
        </div>
      )}

      {hasData && (
        <div className="grid-2">
          {/* Original SEM Scan */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>
              <span className="material-symbols-rounded">image</span>
              ORIGINAL SEM SCAN · WFR-2023-A4
            </div>
            <div className="image-frame" style={{ position: "relative" }}>
              <img src={inspection.input_image} alt="Wafer scan" />
              {/* Scan overlay animation */}
              <div className="scan-overlay">
                <div className="scan-line" />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
              <div className="stat-foot">// SEM High-Res Mode · 12nm Node</div>
              <div className="stat-foot">Source: Optical-B Calibration</div>
            </div>
          </div>

          {/* Inference Result */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>
              <span className="material-symbols-rounded">analytics</span>
              INFERENCE RESULT
            </div>

            <div className="inference-result-panel">
              {/* Class name — large editorial */}
              <div>
                <div className="inference-class-name">
                  {label}
                </div>
                <div className="stat-foot" style={{ marginTop: 8 }}>{description}</div>
              </div>

              {/* Stats row */}
              <div className="inference-row">
                <div className="inference-stat">
                  <div className="inference-stat-label">SEVERITY</div>
                  <span className={`chip ${severityChip}`}>{severity}</span>
                </div>
                <div className="inference-stat">
                  <div className="inference-stat-label">INFERENCE TIME</div>
                  <div className="inference-stat-value">{inspection.inference_time_ms} ms</div>
                </div>
                {inspection.drift_detected && (
                  <div className="inference-stat">
                    <div className="inference-stat-label">DRIFT</div>
                    <span className="chip warn">DETECTED</span>
                  </div>
                )}
              </div>

              {/* Confidence bar */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>Confidence Score</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 14 }}>{confidence}%</span>
                </div>
                <div className="progress thick">
                  <span style={{ width: `${confidence}%` }} />
                </div>
              </div>

              {/* Candidate classes */}
              {(inspection.top_predictions ?? []).length > 0 && (
                <div>
                  <div className="card-title" style={{ marginBottom: 10 }}>
                    <span className="material-symbols-rounded">format_list_numbered</span>
                    CANDIDATE CLASSES
                  </div>
                  <div className="candidate-list">
                    {inspection.top_predictions.map((pred, i) => (
                      <div className="candidate-item" key={i}>
                        <span className="candidate-label">
                          {i + 1}. {pred.label}
                        </span>
                        <div className="progress" style={{ flex: 1 }}>
                          <span style={{ width: `${Math.round(pred.prob * 100)}%` }} />
                        </div>
                        <span className="candidate-pct">{Math.round(pred.prob * 100)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MANUFACTURING METRICS HACKATHON DASHBOARD */}
      {hasData && metrics?.manufacturing_analytics && (
        <div className="card" style={{ marginTop: 24 }}>
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">factory</span>
              MANUFACTURING ANALYTICS
            </div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                color: "var(--muted)",
                border: "1px solid var(--stroke-major)",
                padding: "2px 6px",
                borderRadius: 4
              }}
            >
              FAB-GRADE METRICS
            </div>
          </div>

          <div className="grid-4" style={{ marginTop: 16 }}>
            {/* RTY */}
            <div className="metric-card">
              <div className="metric-label">
                <span className="material-symbols-rounded">model_training</span>
                Rolled Throughput Yield (RTY)
              </div>
              <div className="metric-value">
                {(metrics.manufacturing_analytics.rty.system_rty * 100).toFixed(1)}%
              </div>
              <div className="metric-foot">
                Yield Uplift: +{metrics.manufacturing_analytics.rty.yield_gain_pct}%
              </div>
            </div>

            {/* Defect Density */}
            <div className="metric-card">
              <div className="metric-label">
                <span className="material-symbols-rounded">grid_on</span>
                Defect Density
              </div>
              <div className="metric-value">
                {metrics.manufacturing_analytics.defect_density.current.toFixed(3)} /cm²
              </div>
              <div className="metric-foot">
                Reduced by {metrics.manufacturing_analytics.defect_density.reduction_pct}%
              </div>
            </div>

            {/* GDBN */}
            <div className="metric-card">
              <div className="metric-label">
                <span className="material-symbols-rounded">center_focus_weak</span>
                GDBN Recovery
              </div>
              <div className="metric-value">
                {metrics.manufacturing_analytics.gdbn.recovered_dies_pct}%
              </div>
              <div className="metric-foot">
                Good Dies in Bad Neighborhood
              </div>
            </div>

            {/* Kill Ratio */}
            <div className="metric-card">
              <div className="metric-label">
                <span className="material-symbols-rounded">troubleshoot</span>
                AI Kill Ratio
              </div>
              <div className="metric-value">
                {metrics.manufacturing_analytics.kill_ratio.ai_ratio}
              </div>
              <div className="metric-foot">
                Optical equivalent: {metrics.manufacturing_analytics.kill_ratio.optical_ratio}
              </div>
            </div>
          </div>
          
          <div style={{ padding: "12px", borderTop: "1px dashed var(--stroke-major)", marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span className="material-symbols-rounded" style={{ fontSize: 16, color: "var(--muted)", verticalAlign: "middle", marginRight: 8 }}>fact_check</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text)" }}>
                Incoming Material AQL ({metrics.manufacturing_analytics.aql.threshold_pct}%): 
                <strong className={metrics.manufacturing_analytics.aql.status === "Accept Lot" ? "chip success" : "chip warn"} style={{ marginLeft: 6 }}>
                  {metrics.manufacturing_analytics.aql.status.toUpperCase()}
                </strong>
              </span>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text)", fontWeight: 700 }}>
              Est. Fab Savings: ₹{metrics.manufacturing_analytics.economics.estimated_fab_savings_crore} Crore/yr
            </div>
          </div>
        </div>
      )}

      {hasData && impactResult && (
        <div className="grid-2">
          <ImpactBoard impactResult={impactResult} />
          <ImpactSourceCard impactResult={impactResult} />
        </div>
      )}

      {impactHistory.length > 0 && (
        <ImpactSessionLedger impactHistory={impactHistory} impactSummary={impactSummary} />
      )}

      {/* Historical Comparison */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span className="material-symbols-rounded">compare</span>
            HISTORICAL COMPARISON
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)" }}>
            LAST {histBatches.length || 0} BATCHES
          </div>
        </div>
        {histBatches.length > 0 ? (
          <div className="history-comparison">
            {histBatches.map((batch, i) => (
              <div key={i} className={`history-batch${i === 0 ? " current" : ""}`}>
                <div className="history-batch-id">
                  {i === 0 ? "CURRENT" : `BATCH #${i}`}
                </div>
                <div className="history-batch-class">{batch.defect_class}</div>
                <div className="history-batch-conf">
                  {Math.round(batch.confidence * 100)}% conf
                  {batch.drift_detected ? " · drift" : ""}
                </div>
                <div className="stat-foot" style={{ marginTop: 4 }}>{batch.timestamp}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="stat-foot" style={{ padding: "12px 0" }}>
            // No batch history available yet.
          </div>
        )}
      </div>

      {/* Model Engine Panel */}
      <div className="model-status-widget">
        <span className="material-symbols-rounded" style={{ fontSize: 20, color: "var(--secondary)" }}>memory</span>
        <div>
          <div className="model-status-name">YieldSense v4.2 — Model Engine</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted)", marginTop: 2 }}>
            // 12nm FinFET optimized · TensorRT accelerated
          </div>
        </div>
        <div className="model-status-badge">ONLINE</div>
        <div style={{ marginLeft: "auto" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Last Trained</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", marginTop: 2 }}>
            {histBatches.find((b) => b.retrain_result)?.timestamp ?? "2 days ago"}
          </div>
        </div>
        {hasData && (
          <>
            <div style={{ width: 1, height: 32, background: "var(--stroke-major)" }} />
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>Triage Priority</div>
              <div className={`chip ${inspection.triage?.priority === "high" ? "warn" : "info"}`} style={{ marginTop: 3 }}>
                {inspection.triage?.priority ?? "NORMAL"}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
