function formatTimestampForFilename(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "report";
  }

  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${yyyy}${mm}${dd}-${hh}${min}${ss}`;
}

function sanitizeFilenamePart(value, fallback = "inspection") {
  const normalized = String(value ?? "")
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return normalized || fallback;
}

export function buildAnalysisReport({
  inspection,
  history = [],
  metrics = null,
  impactInputs = null,
  impactResult = null,
  impactHistory = [],
  impactSummary = null,
}) {
  if (!inspection) {
    return null;
  }

  const recentHistory = history.length ? [...history].slice(-10).reverse() : [];
  const confidenceTrend = history.length
    ? history.slice(-24).map((item) => ({
        inspection_id: item.inspection_id,
        confidence: item.confidence,
        defect_class: item.defect_class,
        drift_detected: item.drift_detected,
        timestamp: item.timestamp,
      }))
    : [];

  return {
    report_version: "1.0",
    generated_at: new Date().toISOString(),
    generated_from: "defect-detection-page",
    inspection_id: inspection.inspection_id,
    report_type: "analysis_dashboard_export",
    inspection,
    explainability: {
      heatmap_image: inspection.heatmap_image ?? null,
      triage: inspection.triage ?? null,
      reasoning: inspection.reasoning ?? null,
      ai_insight: inspection.ai_insight ?? null,
    },
    drift: {
      current_inspection: {
        drift_detected: inspection.drift_detected ?? false,
        synth_trigger_mode: inspection.synth_trigger_mode ?? null,
        auto_retrain: inspection.auto_retrain ?? false,
        retrain_result: inspection.retrain_result ?? null,
      },
      dashboard_state: metrics?.drift_state ?? null,
      dashboard_summary: {
        drift_events: metrics?.summary?.drift_events ?? 0,
        avg_confidence: metrics?.summary?.avg_confidence ?? null,
        total_inspections: metrics?.summary?.total_inspections ?? 0,
      },
    },
    dashboard: {
      summary: metrics?.summary ?? null,
      model_metrics: metrics?.model_metrics ?? null,
      recent_inspections: recentHistory,
      confidence_trend: confidenceTrend,
    },
    impact: {
      inputs: impactInputs,
      current_result: impactResult,
      session_history: impactHistory,
      session_summary: impactSummary,
    },
  };
}

export function downloadAnalysisReport(report) {
  if (!report) {
    return;
  }

  const reportBody = JSON.stringify(report, null, 2);
  const blob = new Blob([reportBody], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const inspectionPart = sanitizeFilenamePart(report.inspection_id, "inspection");
  const timestampPart = formatTimestampForFilename(report.generated_at);

  link.href = url;
  link.download = `autoyield-report-${inspectionPart}-${timestampPart}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
