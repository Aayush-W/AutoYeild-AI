import { useInspection } from "../context/InspectionContext.jsx";
import { useNavigate } from "react-router-dom";

export default function DriftMonitoring() {
  const { history, metrics, inspection, refreshDashboard } = useInspection();
  const navigate = useNavigate();
  const driftEvents = history.filter((item) => item.drift_detected);
  const latest = driftEvents.length ? driftEvents[driftEvents.length - 1] : null;
  const driftState = metrics?.drift_state ?? {};

  return (
    <>
      <div className="section-header">
        <div>
          <div className="section-title">Drift Monitoring</div>
          <div className="section-sub">Confidence drift detection and stability tracking</div>
        </div>
        <button className="btn sm" onClick={refreshDashboard}>
          <span className="material-symbols-rounded" style={{ fontSize: 14 }}>refresh</span>
          Refresh
        </button>
      </div>

      {/* Metric cards */}
      <div className="grid-4">
        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">monitor_heart</span>
            Drift Events
          </div>
          <div className="metric-value">{driftEvents.length}</div>
          <div className="metric-foot">
            {driftEvents.length === 0 ? (
              <span className="chip">Stable</span>
            ) : (
              <span className="chip warn">Attention</span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">speed</span>
            Drift Counter
          </div>
          <div className="metric-value">{driftState.low_confidence_count ?? "—"}</div>
          <div className="metric-foot">consecutive triggers</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">tune</span>
            Threshold
          </div>
          <div className="metric-value">
            {driftState.threshold != null
              ? `${Math.round(driftState.threshold * 100)}%`
              : "—"}
          </div>
          <div className="metric-foot">confidence floor</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">check_circle</span>
            Total Inspections
          </div>
          <div className="metric-value">{history.length}</div>
          <div className="metric-foot">in rolling window</div>
        </div>
      </div>

      <div className="grid-2">
        {/* Latest drift event */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">warning</span>
            Latest Drift Event
          </div>
          {latest ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div>
                <div className="stat-foot">Defect Class</div>
                <div style={{ fontWeight: 600, fontSize: 14, textTransform: "capitalize", marginTop: 3 }}>
                  {latest.defect_class}
                </div>
              </div>
              <div>
                <div className="stat-foot">Confidence</div>
                <div style={{ fontWeight: 600, fontSize: 14, marginTop: 3 }}>
                  {Math.round(latest.confidence * 100)}%
                </div>
              </div>
              <div className="progress thick">
                <span style={{ width: `${Math.round(latest.confidence * 100)}%` }} />
              </div>
              <div className="stat-foot">{latest.timestamp}</div>
              <span className="chip warn" style={{ alignSelf: "flex-start" }}>Drift Detected</span>
            </div>
          ) : (
            <div className="stat-foot">No drift events logged yet. System is stable.</div>
          )}
        </div>

        {/* Drift state JSON */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">data_object</span>
            Drift State
          </div>
          <pre
            style={{
              background: "rgba(7,14,26,0.8)",
              borderRadius: "var(--r-md)",
              padding: "12px",
              fontSize: 11,
              color: "var(--muted)",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: 180,
              overflowY: "auto",
            }}
          >
            {Object.keys(driftState).length
              ? JSON.stringify(driftState, null, 2)
              : "{ no drift state — run an analysis first }"}
          </pre>
        </div>
      </div>

      {/* Drift Event Log */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 14 }}>
          <span className="material-symbols-rounded">history</span>
          Drift Event Log
        </div>
        {driftEvents.length > 0 ? (
          <div className="inspection-list">
            {[...driftEvents].reverse().map((event) => (
              <div key={event.inspection_id} className="inspection-item">
                <div className="inspection-left">
                  <div className="badge">
                    <span className="material-symbols-rounded" style={{ fontSize: 14 }}>warning</span>
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12, textTransform: "capitalize" }}>
                      {event.defect_class}
                    </div>
                    <div className="stat-foot">{event.inspection_id}</div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span className="chip warn" style={{ fontSize: 9 }}>Drift</span>
                  <span style={{ fontWeight: 600, fontSize: 12 }}>
                    {Math.round(event.confidence * 100)}%
                  </span>
                  <span className="stat-foot">{event.timestamp}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="stat-foot" style={{ padding: "8px 0" }}>
            Awaiting first drift event. System is operating within normal parameters.
          </div>
        )}
      </div>

      {inspection?.drift_detected && (
        <div className="alert warn">
          <div className="alert-icon">
            <span className="material-symbols-rounded" style={{ color: "var(--warning)" }}>warning</span>
          </div>
          <div className="alert-body">
            <div className="alert-title">Drift Detected on Latest Inspection</div>
            <div className="alert-detail">Synthetic data generation was triggered automatically.</div>
          </div>
          <button className="btn sm" onClick={() => navigate("/synthetic-data")}>
            View Synthetics
          </button>
        </div>
      )}
    </>
  );
}
