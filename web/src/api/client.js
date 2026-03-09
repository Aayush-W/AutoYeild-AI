const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

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

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: form
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Failed to analyze image");
  }

  return response.json();
}

export async function getHistory() {
  const response = await fetch(`${API_BASE}/api/history`);
  if (!response.ok) {
    throw new Error("Failed to load history");
  }
  return response.json();
}

export async function getMetrics() {
  const response = await fetch(`${API_BASE}/api/metrics`);
  if (!response.ok) {
    throw new Error("Failed to load metrics");
  }
  return response.json();
}
