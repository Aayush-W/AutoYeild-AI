import { useEffect, useRef, useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";
import WaferScene from "../components/WaferScene.jsx";
import SemiconductorCursor from "../components/SemiconductorCursor.jsx";
import OverviewIntroOverlay from "../components/OverviewIntroOverlay.jsx";

function Crosshair({ style = {}, className = "" }) {
  return (
    <div
      className={`ov-crosshair ${className}`.trim()}
      style={{
        position: "absolute",
        width: 18,
        height: 18,
        pointerEvents: "none",
        opacity: 0.35,
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: 0,
          right: 0,
          height: 1,
          background: "var(--text)",
          transform: "translateY(-50%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: 0,
          bottom: 0,
          width: 1,
          background: "var(--text)",
          transform: "translateX(-50%)",
        }}
      />
    </div>
  );
}

function TrendBars({ bars }) {
  const max = Math.max(...bars, 1);
  return (
    <div className="trend-bars">
      {bars.map((value, index) => (
        <div
          key={index}
          className="trend-bar"
          style={{ height: `${Math.max(6, (value / max) * 100)}%` }}
          title={`${value}%`}
        />
      ))}
    </div>
  );
}

function TickCount({ value }) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    if (!value) {
      setDisplayed(0);
      return undefined;
    }

    const target = Number(value);
    let current = 0;
    const step = Math.ceil(target / 60);
    const intervalId = setInterval(() => {
      current = Math.min(current + step, target);
      setDisplayed(current);
      if (current >= target) {
        clearInterval(intervalId);
      }
    }, 24);

    return () => clearInterval(intervalId);
  }, [value]);

  return <>{displayed.toLocaleString()}</>;
}

function LocalClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const intervalId = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(intervalId);
  }, []);

  const hhmm = time.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        color: "var(--muted)",
        letterSpacing: "0.1em",
        textAlign: "right",
      }}
    >
      <div
        style={{
          fontSize: 8,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
        }}
      >
        Local Time
      </div>
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: "var(--text)",
          marginTop: 2,
        }}
      >
        {hhmm}
      </div>
    </div>
  );
}

export default function SystemOverview({
  overviewMode = "workspace",
  setOverviewMode,
}) {
  const {
    inspection,
    history,
    metrics,
    refreshDashboard,
    impactSummary,
  } = useInspection();
  const [showIntro, setShowIntro] = useState(true);

  const heroRef = useRef(null);
  const metricsRef = useRef(null);
  const trendRef = useRef(null);
  const tableRef = useRef(null);

  useEffect(() => {
    const intervalId = setInterval(refreshDashboard, 30_000);
    return () => clearInterval(intervalId);
  }, [refreshDashboard]);

  useEffect(() => {
    const elements = [metricsRef.current, trendRef.current, tableRef.current].filter(Boolean);
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          entry.target.classList.toggle("visible", entry.isIntersecting);
        });
      },
      { threshold: 0.1 }
    );

    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const heroElement = heroRef.current;
    if (!heroElement || typeof window === "undefined") {
      return undefined;
    }

    let rafId = 0;
    const updateScrollMotion = () => {
      rafId = 0;
      const rect = heroElement.getBoundingClientRect();
      const waferShift = Math.min(Math.max(-rect.top * 0.12, 0), 26);
      const gridShift = Math.min(Math.max(-rect.top * 0.06, 0), 14);
      heroElement.style.setProperty("--ov-scroll-shift", `${(-waferShift).toFixed(2)}px`);
      heroElement.style.setProperty("--ov-scroll-shift-soft", `${(-gridShift).toFixed(2)}px`);
    };

    const queueUpdate = () => {
      if (!rafId) {
        rafId = window.requestAnimationFrame(updateScrollMotion);
      }
    };

    queueUpdate();
    window.addEventListener("scroll", queueUpdate, { passive: true });
    window.addEventListener("resize", queueUpdate);
    return () => {
      window.removeEventListener("scroll", queueUpdate);
      window.removeEventListener("resize", queueUpdate);
      if (rafId) {
        window.cancelAnimationFrame(rafId);
      }
    };
  }, []);

  const totalInspections = metrics?.summary?.total_inspections ?? 0;
  const avgConf = metrics?.summary?.avg_confidence
    ? `${Math.round(metrics.summary.avg_confidence * 100)}%`
    : "-";
  const driftEvents = metrics?.summary?.drift_events ?? 0;
  const accuracy = metrics?.model_metrics?.accuracy
    ? `${Math.round(metrics.model_metrics.accuracy * 100)}%`
    : "98.4%";

  const bars =
    history.length > 0
      ? history.slice(-24).map((item) => Math.max(10, Math.round(item.confidence * 100)))
      : Array.from({ length: 24 }, (_, i) => 55 + Math.round(Math.sin(i * 0.6) * 20));

  const lastScan = metrics?.summary?.last_inspection?.timestamp ?? inspection?.timestamp ?? "-";
  const telemetryItems = history.length ? [...history].reverse().slice(0, 4) : [];
  const recentInspections = history.length ? [...history].reverse().slice(0, 5) : [];

  const coreThreads = [
    { id: "01", label: "Defect Classification", desc: "Convolutional Visual Engine" },
    { id: "02", label: "Explainability", desc: "GradCAM + Attribution Mapping" },
    { id: "03", label: "Drift Detection", desc: "Statistical Shift Monitoring" },
    { id: "04", label: "Auto-Retraining", desc: "Autonomous Model Adaptation" },
  ];

  return (
    <>
      {showIntro && <OverviewIntroOverlay onComplete={() => setShowIntro(false)} />}
      {overviewMode === "frontpage" && <SemiconductorCursor />}

      <div
        ref={heroRef}
        className={`ov-hero ov-mode-${overviewMode} ${showIntro ? "" : "ov-hero-ready"}`.trim()}
      >
        <Crosshair className="ov-crosshair-1" style={{ top: "12%", left: "18%" }} />
        <Crosshair className="ov-crosshair-2" style={{ top: "28%", left: "7%" }} />
        <Crosshair className="ov-crosshair-3" style={{ top: "65%", left: "3%" }} />
        <Crosshair className="ov-crosshair-4" style={{ top: "80%", left: "22%" }} />
        <Crosshair className="ov-crosshair-5" style={{ top: "10%", right: "14%" }} />
        <Crosshair className="ov-crosshair-6" style={{ top: "72%", right: "5%" }} />
        <Crosshair className="ov-crosshair-7" style={{ top: "40%", right: "18%" }} />

        <div className="ov-topstrip">
          <div className="ov-topstrip-left">
            <div className="ov-kicker">AutoYield AI</div>
          </div>
          <div className="ov-topstrip-center">
            <div className="ov-model-pill">AutoYield-AI</div>
          </div>
          <div className="ov-topstrip-right">
            {overviewMode === "frontpage" && (
              <button
                type="button"
                className="ov-mode-toggle"
                onClick={() => setOverviewMode?.("workspace")}
              >
                OPEN WORKSPACE
              </button>
            )}
            <LocalClock />
          </div>
        </div>

        <div className="ov-left">
          <div className="ov-headline-wrap">
            <h1 className="ov-headline">
              AUTOYIELD-
              <br />
              AI
              <br />
              WAFER
              <br />
              <em>INSPECTION.</em>
            </h1>
            <p className="ov-sub">
              // Next-generation semiconductor defect classification powered by
              proprietary visual reasoning models and multi-modal explainability.
            </p>
          </div>

          <div className="ov-threads">
            <div className="ov-threads-label">[ CORE SYSTEM MODULES ]</div>
            {coreThreads.map((thread, index) => (
              <div
                className="ov-thread-item"
                key={thread.id}
                style={{ animationDelay: `${400 + index * 80}ms` }}
              >
                <div className="ov-thread-id">{thread.id}</div>
                <div className="ov-thread-bar" />
                <div>
                  <div className="ov-thread-label">{thread.label}</div>
                  <div className="ov-thread-desc">{thread.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="ov-wafer-col">
          <WaferScene
            annotationPreset={overviewMode === "workspace" ? "workspace" : "auto"}
            motionLevel="subtle"
          />
        </div>

        <div className="ov-right">
          <div className="ov-def-box">
            <div className="ov-def-box-title">
              AUTOYIELD AI
              <span className="ov-def-box-num">/ 4.2</span>
            </div>
            <div className="ov-def-box-body">
              <div>
                <span className="ov-def-abbr">AUTO</span> (AUTONOMOUS)
              </div>
              <div>
                + <span className="ov-def-abbr">YIELD</span> (SEMICONDUCTOR)
              </div>
              <div className="ov-def-arrow">-&gt; ZERO-DEFECT WAFER YIELD</div>
            </div>
          </div>

          <div className="ov-desc-box">
            <div className="ov-desc-label">NOT A DEMO - LIVE SYSTEM</div>
            <div className="ov-desc-text">
              AutoYield AI is an autonomous semiconductor inspection platform.
              AutoYield-AI runs real-time defect classification, drift
              detection, and self-retraining loops on semiconductor wafer imagery.
            </div>
            <div className="ov-desc-stats">
              <div className="ov-desc-stat">
                <div className="ov-desc-stat-val">{accuracy}</div>
                <div className="ov-desc-stat-label">Accuracy</div>
              </div>
              <div className="ov-desc-stat">
                <div className="ov-desc-stat-val">99.98%</div>
                <div className="ov-desc-stat-label">Uptime</div>
              </div>
              <div className="ov-desc-stat">
                <div className="ov-desc-stat-val">12nm</div>
                <div className="ov-desc-stat-label">Node</div>
              </div>
            </div>
          </div>
        </div>

        <div className="ov-scroll-hint">
          <div>SCROLL TO DASHBOARD</div>
          <span className="material-symbols-rounded">keyboard_arrow_down</span>
        </div>
      </div>

      <div className="section-rule">
        <div className="section-rule-line" />
        <div className="section-rule-text">// INSPECTION_WORKSPACE</div>
        <div className="section-rule-line" />
      </div>

      <div className="engine-banner">
        <div className="engine-banner-left">
          <div className="engine-status-dot" />
          <div>
            <div className="engine-title">Neural Engine v4.2 - AutoYield-AI</div>
            <div className="engine-subtitle">
              // Active diagnostic feed running - real-time inference pipeline
            </div>
          </div>
        </div>
        <div className="engine-stats">
          <div className="engine-stat">
            <div className="engine-stat-label">Uptime</div>
            <div className="engine-stat-value green">90.98%</div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Last Scan</div>
            <div className="engine-stat-value blue" style={{ fontSize: 12 }}>
              {lastScan !== "-" ? lastScan.split(" ")[1] ?? lastScan : "-"}
            </div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Node Status</div>
            <div className="engine-stat-value green" style={{ fontSize: 12 }}>
              HEALTHY
            </div>
          </div>
          <div className="engine-stat">
            <div className="engine-stat-label">Version</div>
            <div className="engine-stat-value" style={{ fontSize: 12 }}>
              v4.2.0-a
            </div>
          </div>
        </div>
      </div>

      <div className="grid-4 reveal" ref={metricsRef}>
        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">trending_up</span>
            Avg Confidence
          </div>
          <div className="metric-value">{avgConf}</div>
          <div className="metric-foot">
            <span className="chip success" style={{ marginRight: 6 }}>
              Stable
            </span>
            Model {accuracy}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">search</span>
            Total Inspections
          </div>
          <div className="metric-value">
            <TickCount value={totalInspections} />
          </div>
          <div className="metric-foot">Rolling window - 200 max</div>
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
          <div
            className="metric-value"
            style={{ fontSize: 22, textTransform: "uppercase" }}
          >
            {inspection?.defect_class ??
              metrics?.summary?.last_inspection?.defect_class ??
              "-"}
          </div>
          <div className="metric-foot">
            {inspection?.confidence != null
              ? `CONF: ${Math.round(inspection.confidence * 100)}%`
              : "// Awaiting analysis"}
          </div>
        </div>
      </div>

      <div className="grid-2 reveal" ref={trendRef}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">show_chart</span>
              Confidence Trend (Last 24 Inspections)
            </div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                color: "var(--muted)",
              }}
            >
              ROLLING WINDOW
            </div>
          </div>
          <TrendBars bars={bars} />
          <div className="stat-foot" style={{ marginTop: 8 }}>
            // Each bar = one inspection. Hover for value.
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="material-symbols-rounded">notifications_active</span>
              Real-time Telemetry
            </div>
          </div>
          {telemetryItems.length > 0 ? (
            <div className="telemetry-feed">
              {telemetryItems.map((item, index) => (
                <div className="telemetry-item" key={index}>
                  <div className={`telemetry-icon ${item.drift_detected ? "warn" : "ok"}`}>
                    <span className="material-symbols-rounded">
                      {item.drift_detected ? "warning" : "check_circle"}
                    </span>
                  </div>
                  <div className="telemetry-body">
                    <div className="telemetry-title" style={{ textTransform: "capitalize" }}>
                      {item.defect_class}
                      {item.drift_detected ? " - Drift Detected" : ""}
                    </div>
                    <div className="telemetry-detail">
                      {item.inspection_id} - Conf: {Math.round(item.confidence * 100)}%
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
                {
                  icon: "check_circle",
                  variant: "ok",
                  title: "Batch #9042 Cleared",
                  detail: "Yield: 99.2%",
                  time: "12:45 PM",
                },
                {
                  icon: "warning",
                  variant: "warn",
                  title: "Thermal Drift Detected",
                  detail: "Node B-12",
                  time: "12:38 PM",
                },
                {
                  icon: "auto_fix_high",
                  variant: "ok",
                  title: "Model Recalibration",
                  detail: "Self-correction applied",
                  time: "12:15 PM",
                },
                {
                  icon: "system_update",
                  variant: "ok",
                  title: "System Update Complete",
                  detail: "v4.2.0-Alpha",
                  time: "11:50 AM",
                },
              ].map((item, index) => (
                <div className="telemetry-item" key={index}>
                  <div className={`telemetry-icon ${item.variant}`}>
                    <span className="material-symbols-rounded">{item.icon}</span>
                  </div>
                  <div className="telemetry-body">
                    <div className="telemetry-title">{item.title}</div>
                    <div className="telemetry-detail">{item.detail}</div>
                  </div>
                  <div className="telemetry-time">{item.time}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {impactSummary.batchesAnalyzed > 0 && (
        <div className="grid-4">
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">bolt</span>
              Session Energy Saved
            </div>
            <div className="metric-value">
              {Math.round(impactSummary.energySavedKwh).toLocaleString()} kWh
            </div>
            <div className="metric-foot">Frontend impact ledger</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">eco</span>
              Session CO2e Prevented
            </div>
            <div className="metric-value">
              {Math.round(impactSummary.carbonPreventedKgco2e).toLocaleString()} kg
            </div>
            <div className="metric-foot">India official factor applied</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">trending_up</span>
              Avg Yield Uplift
            </div>
            <div className="metric-value">{impactSummary.avgYieldUpliftPp.toFixed(2)} pp</div>
            <div className="metric-foot">Batch-level recovery model</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">savings</span>
              Session Cost Saved
            </div>
            <div className="metric-value">
              INR {Math.round(impactSummary.totalCostSavedInr).toLocaleString("en-IN")}
            </div>
            <div className="metric-foot">INR · operator economics inputs</div>
          </div>
        </div>
      )}

      <div className="card reveal" ref={tableRef}>
        <div className="card-header">
          <div className="card-title">
            <span className="material-symbols-rounded">history</span>
            Recent Inspections
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              color: "var(--muted)",
            }}
          >
            LAST {recentInspections.length || 5} RECORDS
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 120px 80px 80px 100px",
            gap: 8,
            padding: "6px 12px",
            borderBottom: "1px solid var(--stroke-major)",
            marginBottom: 6,
          }}
        >
          {["INSPECTION_ID", "CLASS", "CONF", "DRIFT", "TIMESTAMP"].map((header) => (
            <div
              key={header}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                color: "var(--muted)",
                letterSpacing: "0.1em",
              }}
            >
              {header}
            </div>
          ))}
        </div>

        {recentInspections.length > 0 ? (
          <div className="inspection-list">
            {recentInspections.map((item, index) => (
              <div
                className="inspection-item"
                key={index}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 120px 80px 80px 100px",
                  gap: 8,
                  padding: "10px 12px",
                }}
              >
                <div className="inspection-left" style={{ gap: 8 }}>
                  <div className="badge">
                    <span className="material-symbols-rounded">science</span>
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--secondary)",
                    }}
                  >
                    {item.inspection_id}
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    fontWeight: 700,
                    color: "var(--text)",
                    textTransform: "uppercase",
                    display: "flex",
                    alignItems: "center",
                  }}
                >
                  {item.defect_class}
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <div className="progress thick" style={{ flex: 1 }}>
                    <span style={{ width: `${Math.round(item.confidence * 100)}%` }} />
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  {item.drift_detected ? (
                    <span className="chip warn">DRIFT</span>
                  ) : (
                    <span className="chip success">CLEAR</span>
                  )}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--muted)",
                    display: "flex",
                    alignItems: "center",
                  }}
                >
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
