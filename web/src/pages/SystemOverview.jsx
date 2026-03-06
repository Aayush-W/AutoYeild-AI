import { useEffect, useRef } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import WaferScene from "../components/WaferScene.jsx";

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

function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { el.classList.add("visible"); obs.unobserve(el); } },
      { threshold: 0.1 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return ref;
}

export default function SystemOverview() {
  const { inspection, history, metrics, refreshDashboard } = useInspection();

  // Auto-refresh every 30s — PRESERVED
  useEffect(() => {
    const id = setInterval(refreshDashboard, 30_000);
    return () => clearInterval(id);
  }, [refreshDashboard]);

  // Derived values — PRESERVED
  const totalInspections = metrics?.summary?.total_inspections ?? 0;
  const avgConf = metrics?.summary?.avg_confidence
    ? `${Math.round(metrics.summary.avg_confidence * 100)}%`
    : "—";
  const driftEvents = metrics?.summary?.drift_events ?? 0;
  const accuracy = metrics?.model_metrics?.accuracy
    ? `${Math.round(metrics.model_metrics.accuracy * 100)}%`
    : "98.4%";

  const bars =
    history.length > 0
      ? history.slice(-24).map((h) => Math.max(10, Math.round(h.confidence * 100)))
      : Array.from({ length: 24 }, (_, i) => 55 + Math.round(Math.sin(i * 0.6) * 20));

  const lastScan = metrics?.summary?.last_inspection?.timestamp
    ?? inspection?.timestamp
    ?? "—";

  const telemetryItems = history.length
    ? [...history].reverse().slice(0, 5)
    : [];

  const recentInspections = history.length
    ? [...history].reverse().slice(0, 5)
    : [];

  // Reveal refs
  const heroRef = useReveal();
  const metricsRef = useReveal();
  const trendRef = useReveal();
  const tableRef = useReveal();

  return (
    <>
      {/* ── HERO SECTION ── */}
      <div className="hero-section" ref={heroRef} style={{ opacity: 0, transition: "opacity 0.8s ease, transform 0.8s ease" }}>
        <div className="hero-kicker">AutoYield AI · DefectNet-v4.2-TRT</div>

        <h1 className="hero-headline">
          Autonomous Wafer<br />
          <em>Inspection.</em>
        </h1>

        <p className="hero-sub">
          // Next-generation semiconductor defect classification powered by<br />
          proprietary visual reasoning models and multi-modal explainability.
        </p>

        {/* 3D Wafer with annotation callouts */}
        <WaferScene />

        {/* Scroll indicator */}
        <div style={{
          position: "absolute",
          bottom: 32,
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 6,
          animation: "wafer-float 2s ease-in-out infinite",
        }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", letterSpacing: "0.12em", textTransform: "uppercase" }}>
            Scroll to Dashboard
          </div>
          <span className="material-symbols-rounded" style={{ fontSize: 16, color: "var(--muted)" }}>keyboard_arrow_down</span>
        </div>
      </div>

      {/* ── Section divider ── */}
      <div className="section-rule">
        <div className="section-rule-line" />
        <div className="section-rule-text">// INSPECTION_WORKSPACE</div>
        <div className="section-rule-line" />
      </div>

      {/* ── Engine Banner ── */}
      <div className="engine-banner">
        <div className="engine-banner-left">
          <div className="engine-status-dot" />
          <div>
            <div className="engine-title">Neural Engine v4.2 — DefectNet-TRT</div>
            <div className="engine-subtitle">// Active Diagnostic Feed Running · Real-time inference pipeline</div>
          </div>
        </div>
        <div className="engine-stats">
          <div className="engine-stat">
            <div className="engine-stat-label">Uptime</div>
            <div className="engine-stat-value green">99.98%</div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Last Scan</div>
            <div className="engine-stat-value blue" style={{ fontSize: 12 }}>
              {lastScan !== "—" ? lastScan.split(" ")[1] ?? lastScan : "—"}
            </div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Node Status</div>
            <div className="engine-stat-value green" style={{ fontSize: 12 }}>HEALTHY</div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Version</div>
            <div className="engine-stat-value" style={{ fontSize: 12 }}>v4.2.0-α</div>
          </div>
        </div>
      </div>

      {/* ── Metric Cards ── */}
      <div className="grid-4 reveal" ref={metricsRef}>
        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">trending_up</span>
            Avg Confidence
          </div>
          <div className="metric-value">{avgConf}</div>
          <div className="metric-foot">
            <span className="chip success" style={{ marginRight: 6 }}>Stable</span>
            Model {accuracy}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">search</span>
            Total Inspections
          </div>
          <div className="metric-value">{totalInspections.toLocaleString()}</div>
          <div className="metric-foot">Rolling window · 200 max</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">warning</span>
            Drift Events
          </div>
          <div className="metric-value">{driftEvents}</div>
          <div className="metric-foot">
            {driftEvents > 0 ? (
              <span className="chip warn">Attention Required</span>
            ) : (
              <span className="chip success">Normal</span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">bolt</span>
            Latest Class
          </div>
          <div className="metric-value" style={{ fontSize: 22, textTransform: "uppercase" }}>
            {inspection?.defect_class ?? metrics?.summary?.last_inspection?.defect_class ?? "—"}
          </div>
          <div className="metric-foot">
            {inspection?.confidence != null
              ? `CONF: ${Math.round(inspection.confidence * 100)}%`
              : "// Awaiting analysis"}
          </div>
        </div>
      </div>

      {/* ── Confidence Trend + Telemetry ── */}
      <div className="grid-2 reveal" ref={trendRef}>
        {/* Confidence Trend */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">show_chart</span>
              Confidence Trend (Last 24 Inspections)
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)" }}>
              ROLLING WINDOW
            </div>
          </div>
          <TrendBars bars={bars} />
          <div className="stat-foot" style={{ marginTop: 8 }}>
            // Each bar = one inspection. Hover for value.
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
                      {item.inspection_id} · Conf: {Math.round(item.confidence * 100)}%
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

      {/* ── Recent Inspections ── */}
      <div className="card reveal" ref={tableRef}>
        <div className="card-header">
          <div className="card-title">
            <span className="material-symbols-rounded">history</span>
            Recent Inspections
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)" }}>
            LAST {recentInspections.length || 5} RECORDS
          </div>
        </div>

        {/* Column headers */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 120px 80px 80px 100px",
          gap: 8,
          padding: "6px 12px",
          borderBottom: "1px solid var(--stroke-major)",
          marginBottom: 6,
        }}>
          {["INSPECTION_ID", "CLASS", "CONF", "DRIFT", "TIMESTAMP"].map(h => (
            <div key={h} style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>{h}</div>
          ))}
        </div>

        {recentInspections.length > 0 ? (
          <div className="inspection-list">
            {recentInspections.map((item, i) => (
              <div className="inspection-item" key={i} style={{
                display: "grid",
                gridTemplateColumns: "1fr 120px 80px 80px 100px",
                gap: 8,
                padding: "10px 12px",
              }}>
                <div className="inspection-left" style={{ gap: 8 }}>
                  <div className="badge">
                    <span className="material-symbols-rounded">science</span>
                  </div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--secondary)" }}>{item.inspection_id}</div>
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--text)", textTransform: "uppercase", display: "flex", alignItems: "center" }}>{item.defect_class}</div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <div className="progress thick" style={{ flex: 1 }}>
                    <span style={{ width: `${Math.round(item.confidence * 100)}%` }} />
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  {item.drift_detected
                    ? <span className="chip warn">DRIFT</span>
                    : <span className="chip success">CLEAR</span>}
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted)", display: "flex", alignItems: "center" }}>
                  {item.timestamp}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="stat-foot" style={{ padding: "16px 12px" }}>
            // No inspection history yet. Upload a wafer image to begin.
          </div>
        )}
      </div>
    </>
  );
}
