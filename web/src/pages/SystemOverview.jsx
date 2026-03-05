import { useEffect } from "react";
import { useInspection } from "../context/InspectionContext.jsx";

function TrendBars({ bars }) {
  const max = Math.max(...bars, 1);
  return (
    <div className="trend-bars">
      {bars.map((v, i) => (
        <div
          key={i}
          className="trend-bar"
          style={{ height: `${Math.max(6, (v / max) * 100)}%` }}
          title={`${v}%`}
        />
      ))}
    </div>
  );
}

export default function SystemOverview() {
  const { inspection, history, metrics, refreshDashboard } = useInspection();

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(refreshDashboard, 30_000);
    return () => clearInterval(id);
  }, [refreshDashboard]);

  /* ── Derived values ── */
  const totalInspections = metrics?.summary?.total_inspections ?? 0;
  const avgConf = metrics?.summary?.avg_confidence
    ? `${Math.round(metrics.summary.avg_confidence * 100)}%`
    : "—";
  const driftEvents = metrics?.summary?.drift_events ?? 0;
  const accuracy = metrics?.model_metrics?.accuracy
    ? `${Math.round(metrics.model_metrics.accuracy * 100)}%`
    : "98.4%";

  // Confidence trend bars (last 24 inspections)
  const bars =
    history.length > 0
      ? history.slice(-24).map((h) => Math.max(10, Math.round(h.confidence * 100)))
      : Array.from({ length: 24 }, (_, i) => 55 + Math.round(Math.sin(i * 0.6) * 20));

  // Last scan
  const lastScan = metrics?.summary?.last_inspection?.timestamp
    ?? inspection?.timestamp
    ?? "—";

  // Telemetry: most recent 5 history items
  const telemetryItems = history.length
    ? [...history].reverse().slice(0, 5)
    : [];

  // Recent inspections table (last 5)
  const recentInspections = history.length
    ? [...history].reverse().slice(0, 5)
    : [];

  return (
    <>
      {/* Engine Banner */}
      <div className="engine-banner">
        <div className="engine-banner-left">
          <div className="engine-status-dot" />
          <div>
            <div className="engine-title">Neural Engine v4.2</div>
            <div className="engine-subtitle">Active Diagnostic Feed Running</div>
          </div>
        </div>
        <div className="engine-stats">
          <div className="engine-stat">
            <div className="engine-stat-label">Uptime</div>
            <div className="engine-stat-value green">99.98%</div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Last Scan</div>
            <div className="engine-stat-value blue" style={{ fontSize: 13 }}>
              {lastScan !== "—" ? lastScan.split(" ")[1] ?? lastScan : "—"}
            </div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Node Status</div>
            <div className="engine-stat-value green" style={{ fontSize: 13 }}>Healthy</div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Version</div>
            <div className="engine-stat-value" style={{ fontSize: 13 }}>v4.2.0-A</div>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid-4">
        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">trending_up</span>
            Avg Confidence
          </div>
          <div className="metric-value">{avgConf}</div>
          <div className="metric-foot">
            <span className="chip info" style={{ marginRight: 6 }}>Stable</span>
            Model {accuracy}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">search</span>
            Total Inspections
          </div>
          <div className="metric-value">{totalInspections.toLocaleString()}</div>
          <div className="metric-foot">rolling window • 200 max</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">warning</span>
            Drift Events
          </div>
          <div className="metric-value">{driftEvents}</div>
          <div className="metric-foot">
            {driftEvents > 0 ? (
              <span className="chip warn">Attention</span>
            ) : (
              <span className="chip">Normal</span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">bolt</span>
            Latest Class
          </div>
          <div
            className="metric-value"
            style={{ fontSize: 18, textTransform: "capitalize" }}
          >
            {inspection?.defect_class ?? metrics?.summary?.last_inspection?.defect_class ?? "—"}
          </div>
          <div className="metric-foot">
            {inspection?.confidence != null
              ? `Conf: ${Math.round(inspection.confidence * 100)}%`
              : "Run an analysis"}
          </div>
        </div>
      </div>

      {/* Trend + Telemetry */}
      <div className="grid-2">
        {/* Confidence Trend */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">show_chart</span>
              Confidence Trend (Last 24 Inspections)
            </div>
          </div>
          <TrendBars bars={bars} />
          <div className="stat-foot" style={{ marginTop: 8 }}>
            Each bar = one inspection. Hover for value.
          </div>
        </div>

        {/* Telemetry Feed */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">notifications_active</span>
              Real-time Telemetry
            </div>
          </div>
          {telemetryItems.length > 0 ? (
            <div className="telemetry-feed">
              {telemetryItems.map((item, i) => (
                <div className="telemetry-item" key={i}>
                  <div className={`telemetry-icon ${item.drift_detected ? "warn" : "ok"}`}>
                    <span className="material-symbols-rounded">
                      {item.drift_detected ? "warning" : "check_circle"}
                    </span>
                  </div>
                  <div className="telemetry-body">
                    <div className="telemetry-title" style={{ textTransform: "capitalize" }}>
                      {item.defect_class}
                      {item.drift_detected ? " — Drift Detected" : ""}
                    </div>
                    <div className="telemetry-detail">
                      {item.inspection_id} • Conf: {Math.round(item.confidence * 100)}%
                    </div>
                  </div>
                  <div className="telemetry-time">
                    {item.timestamp?.split(" ")[1] ?? item.timestamp}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="telemetry-feed">
              {[
                { icon: "check_circle", variant: "ok", title: "Batch #9042 Cleared", detail: "Yield: 99.2%", time: "12:45 PM" },
                { icon: "warning", variant: "warn", title: "Thermal Drift Detected", detail: "Node B-12", time: "12:38 PM" },
                { icon: "auto_fix_high", variant: "ok", title: "Model Recalibration", detail: "Self-correction applied", time: "12:15 PM" },
                { icon: "system_update", variant: "ok", title: "System Update Complete", detail: "v4.2.0-Alpha", time: "11:50 AM" },
              ].map((t, i) => (
                <div className="telemetry-item" key={i}>
                  <div className={`telemetry-icon ${t.variant}`}>
                    <span className="material-symbols-rounded">{t.icon}</span>
                  </div>
                  <div className="telemetry-body">
                    <div className="telemetry-title">{t.title}</div>
                    <div className="telemetry-detail">{t.detail}</div>
                  </div>
                  <div className="telemetry-time">{t.time}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Inspections */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span className="material-symbols-rounded">history</span>
            Recent Inspections
          </div>
        </div>
        {recentInspections.length > 0 ? (
          <div className="inspection-list">
            {recentInspections.map((item, i) => (
              <div className="inspection-item" key={i}>
                <div className="inspection-left">
                  <div className="badge">
                    <span className="material-symbols-rounded">science</span>
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12, textTransform: "capitalize" }}>
                      {item.defect_class}
                    </div>
                    <div className="stat-foot">{item.inspection_id}</div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <div
                    className="progress"
                    style={{ width: 100 }}
                    title={`${Math.round(item.confidence * 100)}%`}
                  >
                    <span style={{ width: `${Math.round(item.confidence * 100)}%` }} />
                  </div>
                  <span className="stat-foot">
                    {Math.round(item.confidence * 100)}%
                  </span>
                  {item.drift_detected && (
                    <span className="chip warn" style={{ fontSize: 9 }}>Drift</span>
                  )}
                  <span className="stat-foot">{item.timestamp}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="stat-foot" style={{ padding: "12px 0" }}>
            No inspection history yet. Upload a wafer image to begin.
          </div>
        )}
      </div>
    </>
  );
}
