import StatCard from "../components/StatCard.jsx";
import TrendChart from "../components/TrendChart.jsx";
import InspectionList from "../components/InspectionList.jsx";
import AlertList from "../components/AlertList.jsx";
import { trendBars as mockBars, inspections as mockInspections, alerts as mockAlerts } from "../data/mock.js";
import { useInspection } from "../context/InspectionContext.jsx";

export default function SystemOverview() {
  const { inspection, history, metrics } = useInspection();
  const lastInspection = metrics?.summary?.last_inspection?.timestamp || inspection?.timestamp || "\u2014";
  const avgConfidence = metrics?.summary?.avg_confidence
    ? `${Math.round(metrics.summary.avg_confidence * 100)}%`
    : "95%";
  const activeAlerts = metrics?.summary?.drift_events?.toString() || (inspection?.drift_detected ? "1" : "0");
  const bars = history.length
    ? history.slice(-24).map((item) => Math.max(10, Math.round(item.confidence * 100)))
    : mockBars;
  const inspectionItems = history.length
    ? history
        .slice(-5)
        .reverse()
        .map((item, idx) => ({
          id: idx,
          label: item.defect_class,
          time: item.timestamp,
          score: Math.round(item.confidence * 100)
        }))
    : mockInspections;

  const accuracy = metrics?.model_metrics?.accuracy;
  return (
    <>
      <div className="card" style={{ display: "flex", gap: 16, alignItems: "center" }}>
        <div className="chip">Running</div>
        <div style={{ color: "var(--muted)" }}>Model: v2.1.0</div>
        <div style={{ marginLeft: "auto", color: "var(--muted)" }}>
          Last Inspection: <strong>{lastInspection}</strong>
        </div>
      </div>

      <div className="grid-4">
        <StatCard title="System Status" value="Running" chip="Stable" />
        <StatCard
          title="Model Version"
          value="v2.1.0"
          foot={accuracy ? `Accuracy ${Math.round(accuracy * 100)}%` : "Last updated 2h ago"}
        />
        <StatCard title="Avg Confidence" value={avgConfidence} chip="+2.3%" chipVariant="info" />
        <StatCard title="Active Alerts" value={activeAlerts} chip="Attention" chipVariant="warn" />
      </div>

      <div className="grid-2">
        <TrendChart bars={bars} />
        <InspectionList items={inspectionItems} />
      </div>

      <AlertList
        alerts={
          inspection?.drift_detected
            ? [
                {
                  id: 99,
                  variant: "warn",
                  title: "Drift detected on latest inspection",
                  detail: "Synthetic data generation triggered",
                  time: inspection.timestamp
                },
                ...mockAlerts
              ]
            : mockAlerts
        }
      />
    </>
  );
}
