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

export function buildAnalysisReportPayload({
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
    inspection: {
      ...inspection,
      input_image: inspection.input_image ?? null,
      heatmap_image: inspection.heatmap_image ?? null,
    },
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
      manufacturing_analytics: metrics?.manufacturing_analytics ?? null,
    },
    impact: {
      inputs: impactInputs,
      current_result: impactResult,
      session_history: impactHistory,
      session_summary: impactSummary,
    },
  };
}

function escapePdfText(value) {
  return String(value ?? "")
    .replace(/[^\x20-\x7E]/g, " ")
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)")
    .replace(/\r?\n/g, " ");
}

function wrapText(text, maxChars) {
  const normalized = String(text ?? "").trim();
  if (!normalized) {
    return [""];
  }

  const paragraphs = normalized.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
  const lines = [];

  paragraphs.forEach((paragraph, paragraphIndex) => {
    const words = paragraph.split(/\s+/);
    let current = "";

    words.forEach((word) => {
      const candidate = current ? `${current} ${word}` : word;
      if (candidate.length > maxChars && current) {
        lines.push(current);
        current = word;
      } else {
        current = candidate;
      }
    });

    if (current) {
      lines.push(current);
    }

    if (paragraphIndex < paragraphs.length - 1) {
      lines.push("");
    }
  });

  return lines.length ? lines : [""];
}

function bulletItems(items = [], prefix = "-") {
  return (items ?? []).filter(Boolean).map((item) => `${prefix} ${item}`);
}

function buildPdfLineItems(report) {
  const items = [];
  const pushWrapped = (text, fontSize = 11, options = {}) => {
    const {
      indent = 0,
      gapBefore = 0,
      gapAfter = 0,
      bold = false,
    } = options;
    const maxChars = Math.max(32, Math.floor((510 - indent) / Math.max(fontSize * 0.56, 1)));
    const wrappedLines = wrapText(text, maxChars);
    wrappedLines.forEach((line, index) => {
      items.push({
        text: line,
        fontSize,
        indent,
        bold,
        gapBefore: index === 0 ? gapBefore : 0,
        gapAfter: index === wrappedLines.length - 1 ? gapAfter : 0,
      });
    });
  };

  const title = report.title_section?.title || "AUTOYIELD AI - WAFER DEFECT INSPECTION REPORT";
  pushWrapped(title, 18, { gapAfter: 8, bold: true });
  pushWrapped(`Inspection ID: ${report.title_section?.inspection_id || report.inspection_id || "inspection"}`, 10, { bold: true });
  pushWrapped(`Generated: ${report.title_section?.generated || report.generated_at || new Date().toISOString()}`, 10);
  pushWrapped(`Model: ${report.title_section?.model || report.llm?.model || "gemini"}`, 10);
  pushWrapped(`Inference Time: ${report.title_section?.inference_time || "0.0 seconds"}`, 10, { gapAfter: 12 });

  const section = (heading) => pushWrapped(heading, 14, { gapBefore: 2, gapAfter: 4, bold: true });
  const bullets = (values, options = {}) => {
    bulletItems(values).forEach((line) => {
      pushWrapped(line, 11, { indent: 12, ...options });
    });
    items.push({ text: "", fontSize: 8, bold: false, gapAfter: 6 });
  };

  section("Inspection Metadata");
  bullets(report.inspection_metadata);

  section("Executive Summary");
  bullets(report.executive_summary);

  section("Key Findings");
  bullets(report.key_findings);

  section("Inspection Details");
  bullets(report.inspection_details);

  section("Model Predictions");
  pushWrapped("Model Prediction Ranking", 12, { bold: true, gapAfter: 2 });
  (report.model_predictions?.ranking ?? []).forEach((item) => {
    pushWrapped(`${item.label} - ${item.confidence} confidence`, 11, { indent: 12 });
  });
  items.push({ text: "", fontSize: 8, bold: false, gapAfter: 4 });
  pushWrapped("Interpretation", 12, { bold: true, gapAfter: 2 });
  bullets(report.model_predictions?.interpretation);

  section("Explainability Insights");
  pushWrapped("Explainability Summary", 12, { bold: true, gapAfter: 2 });
  bullets(report.explainability_insights?.summary);
  pushWrapped("Interpretation", 12, { bold: true, gapAfter: 2 });
  bullets(report.explainability_insights?.interpretation);

  section("Drift & Model Health");
  pushWrapped("Drift Monitoring", 12, { bold: true, gapAfter: 2 });
  bullets(report.drift_model_health?.drift_monitoring);
  pushWrapped("Model Performance Metrics", 12, { bold: true, gapAfter: 2 });
  bullets(report.drift_model_health?.model_performance_metrics);
  pushWrapped("Recent Inspection History", 12, { bold: true, gapAfter: 2 });
  bullets(report.drift_model_health?.recent_inspection_history);

  section("Operational Impact");
  pushWrapped("Operational Impact Estimates", 12, { bold: true, gapAfter: 2 });
  bullets(report.operational_impact?.estimates);
  pushWrapped("Session Statistics", 12, { bold: true, gapAfter: 2 });
  bullets(report.operational_impact?.session_statistics);
  if (report.operational_impact?.note) {
    pushWrapped(`Note: ${report.operational_impact.note}`, 10, { indent: 12, gapAfter: 8 });
  }

  section("Recommended Engineering Actions");
  (report.recommended_engineering_actions?.actions ?? []).forEach((item, index) => {
    pushWrapped(`${index + 1}. ${item}`, 11, { indent: 12 });
  });
  items.push({ text: "", fontSize: 8, bold: false, gapAfter: 4 });
  pushWrapped("Escalation Trigger", 12, { bold: true, gapAfter: 2 });
  bullets(report.recommended_engineering_actions?.escalation_trigger);

  section("Appendix (Technical Metrics)");
  bullets(report.appendix_technical_metrics);

  return items;
}

function buildPdfBlob(report) {
  const pageWidth = 612;
  const pageHeight = 792;
  const margin = 48;
  const footerHeight = 24;
  const usableBottom = margin + footerHeight;
  const lineItems = buildPdfLineItems(report);
  const pages = [];
  let currentPage = [];
  let y = pageHeight - margin;

  lineItems.forEach((item) => {
    const lineHeight = Math.max(item.fontSize * 1.45, 12);
    const requiredHeight = (item.gapBefore || 0) + lineHeight + (item.gapAfter || 0);

    if (y - requiredHeight < usableBottom) {
      pages.push(currentPage);
      currentPage = [];
      y = pageHeight - margin;
    }

    y -= item.gapBefore || 0;
    currentPage.push({
      text: item.text,
      fontSize: item.fontSize,
      x: margin + (item.indent || 0),
      y,
    });
    y -= lineHeight;
    y -= item.gapAfter || 0;
  });

  if (currentPage.length > 0) {
    pages.push(currentPage);
  }

  const objects = [null, null];
  const normalFontObjectNumber = 3;
  const boldFontObjectNumber = 4;
  objects[normalFontObjectNumber - 1] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>";
  objects[boldFontObjectNumber - 1] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>";

  const pageObjectNumbers = [];

  pages.forEach((pageLines, pageIndex) => {
    const footerY = 28;
    const contentCommands = pageLines
      .map(
        (line) =>
          `BT /${line.bold ? "F2" : "F1"} ${line.fontSize} Tf 1 0 0 1 ${line.x.toFixed(2)} ${line.y.toFixed(2)} Tm (${escapePdfText(line.text)}) Tj ET`
      )
      .concat([
        `BT /F1 9 Tf 1 0 0 1 ${margin.toFixed(2)} ${footerY.toFixed(2)} Tm (AutoYield AI technical inspection PDF) Tj ET`,
        `BT /F1 9 Tf 1 0 0 1 ${(pageWidth - margin - 60).toFixed(2)} ${footerY.toFixed(2)} Tm (Page ${pageIndex + 1} of ${pages.length}) Tj ET`,
      ])
      .join("\n");

    const contentObjectNumber = objects.length + 1;
    objects.push(`<< /Length ${contentCommands.length} >>\nstream\n${contentCommands}\nendstream`);

    const pageObjectNumber = objects.length + 1;
    pageObjectNumbers.push(pageObjectNumber);
    objects.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /Font << /F1 ${normalFontObjectNumber} 0 R /F2 ${boldFontObjectNumber} 0 R >> >> /Contents ${contentObjectNumber} 0 R >>`
    );
  });

  objects[0] = "<< /Type /Catalog /Pages 2 0 R >>";
  objects[1] = `<< /Type /Pages /Kids [${pageObjectNumbers.map((num) => `${num} 0 R`).join(" ")}] /Count ${pageObjectNumbers.length} >>`;

  let pdf = "%PDF-1.4\n";
  const offsets = [0];

  objects.forEach((objectBody, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${objectBody}\nendobj\n`;
  });

  const xrefOffset = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += "0000000000 65535 f \n";
  offsets.slice(1).forEach((offset) => {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  });
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;

  return new Blob([pdf], { type: "application/pdf" });
}

export function downloadAnalysisReport(fileBundle) {
  if (!fileBundle?.blob) {
    return;
  }

  let url;
  try {
    url = URL.createObjectURL(fileBundle.blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileBundle.filename || "AutoYield_AI_Inspection_Report.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();

  } catch (err) {
    console.error("Failed to trigger PDF download:", err);
  } finally {
    if (url) {
      setTimeout(() => URL.revokeObjectURL(url), 100);
    }
  }
}

