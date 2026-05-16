import { useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import { generateAnalysisReport } from "../api/client.js";
import { buildAnalysisReportPayload, downloadAnalysisReport } from "../utils/reportBuilder.js";

export default function LogsArtifacts() {
  const {
    inspection,
    history,
    metrics,
    refreshDashboard,
    impactInputs,
    impactResult,
    impactHistory,
    impactSummary,
  } = useInspection();
  const [activeTab, setActiveTab] = useState("inspection");
  const [reportLoading, setReportLoading] = useState(false);

  const tabs = [
    { key: "inspection", label: "Latest Inspection", icon: "science" },
    { key: "model_metrics", label: "Model Metrics", icon: "bar_chart" },
    { key: "history", label: "History (last 10)", icon: "history" },
  ];

  const content = {
    inspection: inspection
      ? JSON.stringify(
        // Omit base64 blobs from display
        {
          ...inspection,
          input_image: "[base64 omitted]",
          heatmap_image: "[base64 omitted]",
          synthetic_images: `[${inspection.synthetic_images?.length ?? 0} images omitted]`,
        },
        null,
        2
      )
      : "No inspection data yet.",
    model_metrics: metrics?.model_metrics
      ? JSON.stringify(metrics.model_metrics, null, 2)
      : "No model metrics found.",
    history: history.length
      ? JSON.stringify(
        [...history]
          .reverse()
          .slice(0, 10)
          .map((h) => ({
            ...h,
            // Omit heavy fields
            input_image: undefined,
            heatmap_image: undefined,
          })),
        null,
        2
      )
      : "History is empty.",
  };

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
      <div className="section-header">
        <div>
          <div className="section-title">Logs &amp; Artifacts</div>
          <div className="section-sub">Raw API payloads and model metrics</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn sm" onClick={handleDownloadReport} disabled={!inspection || reportLoading}>
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>
              {reportLoading ? "hourglass_top" : "download"}
            </span>
            {reportLoading ? "Generating PDF..." : "Download PDF"}
          </button>
          <button className="btn sm" onClick={refreshDashboard}>
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>refresh</span>
            Refresh
          </button>
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid-4">
        {[
          { label: "Total Inspections", value: metrics?.summary?.total_inspections ?? 0, icon: "science" },
          {
            label: "Avg Confidence",
            value: metrics?.summary?.avg_confidence
              ? `${Math.round(metrics.summary.avg_confidence * 100)}%`
              : "—",
            icon: "trending_up"
          },
          { label: "Drift Events", value: metrics?.summary?.drift_events ?? 0, icon: "warning" },
          {
            label: "Class Distribution",
            value: Object.keys(metrics?.summary?.class_distribution ?? {}).length,
            icon: "category"
          },
        ].map((s) => (
          <div className="metric-card" key={s.label}>
            <div className="metric-label">
              <span className="material-symbols-rounded">{s.icon}</span>
              {s.label}
            </div>
            <div className="metric-value">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: "flex",
          gap: 4,
          background: "rgba(7,14,26,0.7)",
          border: "1px solid var(--stroke)",
          borderRadius: "var(--r-md)",
          padding: 4,
          width: "fit-content",
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`btn sm${activeTab === tab.key ? " primary" : ""}`}
            onClick={() => setActiveTab(tab.key)}
            style={{ textTransform: "none" }}
          >
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* JSON viewer */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 12 }}>
          <span className="material-symbols-rounded">code</span>
          {tabs.find((t) => t.key === activeTab)?.label}
        </div>
        <pre
          style={{
            background: "rgba(4,8,18,0.9)",
            borderRadius: "var(--r-md)",
            padding: "16px",
            fontSize: 11.5,
            color: "#7bbff5",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            maxHeight: 460,
            overflowY: "auto",
            lineHeight: 1.6,
            fontFamily: "'Courier New', monospace",
          }}
        >
          {content[activeTab]}
        </pre>
      </div>

      {/* Class distribution */}
      {metrics?.summary?.class_distribution &&
        Object.keys(metrics.summary.class_distribution).length > 0 && (
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>
              <span className="material-symbols-rounded">donut_large</span>
              Class Distribution
            </div>
            <div className="candidate-list">
              {Object.entries(metrics.summary.class_distribution)
                .sort(([, a], [, b]) => b - a)
                .map(([cls, count]) => {
                  const pct = Math.round((count / (metrics.summary.total_inspections || 1)) * 100);
                  return (
                    <div className="candidate-item" key={cls}>
                      <span
                        className="candidate-label"
                        style={{ textTransform: "capitalize" }}
                      >
                        {cls}
                      </span>
                      <div className="progress" style={{ flex: 1 }}>
                        <span style={{ width: `${pct}%` }} />
                      </div>
                      <span className="candidate-pct">{pct}%</span>
                      <span className="stat-foot" style={{ width: 30 }}>×{count}</span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
    </>
  );
}
