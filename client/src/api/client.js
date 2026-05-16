const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_BASE = RAW_API_BASE.replace(/\/+$/, "");
const API_ROOT = API_BASE.endsWith("/api") ? API_BASE.slice(0, -4) : API_BASE;

function apiUrl(path) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_ROOT}${normalized}`;
}

async function fetchWithRouteFallback(primaryPath, fallbackPath, options = {}) {
  const primaryResponse = await fetch(apiUrl(primaryPath), options);
  if (primaryResponse.status !== 404 || !fallbackPath) {
    return primaryResponse;
  }
  return fetch(apiUrl(fallbackPath), options);
}

async function readErrorPayload(response, fallback) {
  const text = await response.text();
  if (!text) {
    return fallback;
  }
  try {
    const parsed = JSON.parse(text);
    if (parsed?.detail) {
      return String(parsed.detail);
    }
  } catch {
    // best effort parsing only
  }
  return text;
}

export async function analyzeImage(file, options = {}) {
  const form = new FormData();
  form.append("file", file);
  form.append("confidence_threshold", options.confidenceThreshold ?? 0.45);
  form.append("max_low_confidence", options.maxLowConfidence ?? 1);
  form.append("synth_trigger_mode", options.synthTriggerMode ?? "above");
  form.append("synth_count", options.synthCount ?? 10);
  form.append("synth_size", options.synthSize ?? 64);
  form.append("auto_retrain", options.autoRetrain ?? false);
  form.append("retrain_epochs", options.retrainEpochs ?? 1);
  form.append("min_accuracy_delta", options.minAccuracyDelta ?? 0.0);

  const response = await fetch(apiUrl("/api/analyze"), {
    method: "POST",
    body: form
  });

  if (!response.ok) {
    const text = await readErrorPayload(response, "Failed to analyze image");
    throw new Error(text || "Failed to analyze image");
  }

  return response.json();
}

export async function getHistory() {
  const response = await fetch(apiUrl("/api/history"));
  if (!response.ok) {
    throw new Error("Failed to load history");
  }
  return response.json();
}

export async function getMetrics() {
  const response = await fetch(apiUrl("/api/metrics"));
  if (!response.ok) {
    throw new Error("Failed to load metrics");
  }
  return response.json();
}

export async function generateAnalysisReport(reportPayload) {
  const response = await fetch(apiUrl("/api/report"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(reportPayload),
  });

  if (!response.ok) {
    const text = await readErrorPayload(response, "Failed to generate report");
    throw new Error(text || "Failed to generate report");
  }

  const contentDisposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = contentDisposition.match(/filename="([^"]+)"/i);
  const filename = filenameMatch?.[1] || "AutoYield_AI_Inspection_Report.pdf";
  const blob = await response.blob();

  return { blob, filename };
}

export async function getRetrainReviewQueue() {
  const response = await fetch(apiUrl("/api/retrain/review-queue"));
  if (!response.ok) {
    throw new Error("Failed to load review queue");
  }
  return response.json();
}

export async function submitReviewLabel(reviewId, expertLabel) {
  const response = await fetch(apiUrl(`/api/retrain/review-queue/${reviewId}/submit`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ expert_label: expertLabel }),
  });

  if (!response.ok) {
    const text = await readErrorPayload(response, "Failed to submit expert label");
    throw new Error(text || "Failed to submit expert label");
  }

  return response.json();
}

export async function markReviewReviewed(reviewId) {
  const response = await fetch(apiUrl(`/api/retrain/review-queue/${reviewId}/mark-reviewed`), {
    method: "POST",
  });

  if (!response.ok) {
    const text = await readErrorPayload(response, "Failed to mark review as reviewed");
    throw new Error(text || "Failed to mark review as reviewed");
  }

  return response.json();
}

// ── Batch Inspection ─────────────────────────────────────────────────────────

export async function startBatchInspection(formData) {
  const response = await fetchWithRouteFallback("/api/batch_predict", "/batch_predict", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const message = await readErrorPayload(response, "Failed to start batch inspection");
    const error = new Error(message || "Failed to start batch inspection");
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export async function getBatchInspectionStatus(jobId) {
  const response = await fetchWithRouteFallback(
    `/api/batch_predict/${jobId}`,
    `/batch_predict/${jobId}`
  );
  if (!response.ok) {
    const message = await readErrorPayload(response, "Failed to get batch job status");
    const error = new Error(message || "Failed to get batch job status");
    error.status = response.status;
    throw error;
  }
  return response.json();
}
