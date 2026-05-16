import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  getRetrainReviewQueue,
  markReviewReviewed,
  submitReviewLabel,
} from "../api/client.js";
import { useInspection } from "../context/InspectionContext.jsx";

const FALLBACK_LABEL_OPTIONS = [
  "Center",
  "Donut",
  "Edge Loc",
  "Edge Ring",
  "Local",
  "Near Full",
  "Particle",
  "Random",
  "Scratch",
  "Clean",
  "Other / Unknown",
];

function statusChipClass(item) {
  if (item.verification_status || item.status === "verified_by_expert") {
    return "success";
  }
  return "warn";
}

function statusLabel(item) {
  if (item.verification_status || item.status === "verified_by_expert") {
    return "Verified by Expert";
  }
  return "Pending Review";
}

function formatConfidence(value) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

const queueGridColumns = "108px 168px 150px 120px 190px 176px 170px 190px";

export default function AutoRetraining() {
  const { history, inspection } = useInspection();
  const navigate = useNavigate();
  const retrainCandidates = history.filter((item) => item.drift_detected);
  const latestTrigger = retrainCandidates.length
    ? retrainCandidates[retrainCandidates.length - 1]
    : null;
  const retrainResult = inspection?.retrain_result ?? null;

  const [queueItems, setQueueItems] = useState([]);
  const [queueStats, setQueueStats] = useState({
    high_confidence_samples: 0,
    medium_confidence_samples: 0,
    awaiting_expert_review: 0,
    human_verified_samples: 0,
  });
  const [labelOptions, setLabelOptions] = useState(FALLBACK_LABEL_OPTIONS);
  const [draftLabels, setDraftLabels] = useState({});
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [busyRow, setBusyRow] = useState("");

  async function loadQueue() {
    setLoadingQueue(true);
    setQueueError("");
    try {
      const payload = await getRetrainReviewQueue();
      setQueueItems(payload.queue ?? []);
      setQueueStats(payload.stats ?? {});
      setLabelOptions(payload.label_options?.length ? payload.label_options : FALLBACK_LABEL_OPTIONS);
    } catch (error) {
      setQueueError(error.message || "Failed to load verification queue.");
    } finally {
      setLoadingQueue(false);
    }
  }

  useEffect(() => {
    loadQueue();
  }, [inspection?.inspection_id]);

  async function handleSubmitLabel(item) {
    const expertLabel = draftLabels[item.review_id] ?? item.expert_label ?? "";
    if (!expertLabel) {
      setQueueError("Select an expert label before submitting.");
      return;
    }

    setBusyRow(item.review_id);
    setQueueError("");
    try {
      const result = await submitReviewLabel(item.review_id, expertLabel);
      setQueueItems(result.queue_payload?.queue ?? []);
      setQueueStats(result.queue_payload?.stats ?? {});
      setLabelOptions(result.queue_payload?.label_options?.length ? result.queue_payload.label_options : FALLBACK_LABEL_OPTIONS);
    } catch (error) {
      setQueueError(error.message || "Failed to submit expert label.");
    } finally {
      setBusyRow("");
    }
  }

  async function handleMarkReviewed(item) {
    setBusyRow(item.review_id);
    setQueueError("");
    try {
      const result = await markReviewReviewed(item.review_id);
      setQueueItems(result.queue_payload?.queue ?? []);
      setQueueStats(result.queue_payload?.stats ?? {});
      setLabelOptions(result.queue_payload?.label_options?.length ? result.queue_payload.label_options : FALLBACK_LABEL_OPTIONS);
    } catch (error) {
      setQueueError(error.message || "Failed to update review status.");
    } finally {
      setBusyRow("");
    }
  }

  return (
    <>
      <div className="section-header">
        <div>
          <div className="section-title">Auto-Retraining</div>
          <div className="section-sub">Automated model retraining readiness and trigger log</div>
        </div>
        <button className="btn primary sm" onClick={() => navigate("/ingestion")}>
          <span className="material-symbols-rounded" style={{ fontSize: 14 }}>add</span>
          New Analysis
        </button>
      </div>

      <div className="grid-4">
        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">pending</span>
            Retrain Queue
          </div>
          <div className="metric-value">{retrainCandidates.length}</div>
          <div className="metric-foot">drift events pending</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">check_circle</span>
            Status
          </div>
          <div className="metric-value" style={{ fontSize: 16 }}>
            {retrainResult ? "Retrained" : "Standby"}
          </div>
          <div className="metric-foot">
            {retrainResult ? (
              <span className="chip">Done</span>
            ) : (
              <span className="chip info">Idle</span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">bolt</span>
            Synthetics Used
          </div>
          <div className="metric-value">{inspection?.synthetic_count ?? 0}</div>
          <div className="metric-foot">this session</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">
            <span className="material-symbols-rounded">auto_mode</span>
            Auto Retrain
          </div>
          <div className="metric-value" style={{ fontSize: 16 }}>
            {inspection?.auto_retrain ? "On" : "Off"}
          </div>
          <div className="metric-foot">configured in ingestion</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">schedule</span>
            Latest Trigger
          </div>
          {latestTrigger ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div>
                <div className="stat-foot">Defect Class</div>
                <div style={{ fontWeight: 600, fontSize: 14, textTransform: "capitalize", marginTop: 3 }}>
                  {latestTrigger.defect_class}
                </div>
              </div>
              <div className="stat-foot">{latestTrigger.timestamp}</div>
              <div className="progress thick">
                <span style={{ width: `${Math.round(latestTrigger.confidence * 100)}%` }} />
              </div>
              <div className="stat-foot">
                Confidence: {Math.round(latestTrigger.confidence * 100)}%
              </div>
              <span className="chip warn" style={{ alignSelf: "flex-start" }}>Drift Triggered</span>
            </div>
          ) : (
            <div className="stat-foot">No retraining triggers yet. System is stable.</div>
          )}
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>
            <span className="material-symbols-rounded">model_training</span>
            Latest Retrain Result
          </div>
          {retrainResult ? (
            <pre
              style={{
                background: "rgba(7,14,26,0.8)",
                borderRadius: "var(--r-md)",
                padding: "12px",
                fontSize: 11,
                color: "var(--muted)",
                whiteSpace: "pre-wrap",
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {JSON.stringify(retrainResult, null, 2)}
            </pre>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="stat-foot">No retrain has executed yet this session.</div>
              <div className="advisory-banner" style={{ marginTop: 8 }}>
                <span className="material-symbols-rounded">info</span>
                <div>
                  <div className="advisory-label">How to trigger</div>
                  <div className="advisory-text">
                    Enable &ldquo;Auto Retrain&rdquo; in the Engine Parameters panel on the
                    Image Ingestion page, then upload a wafer scan. Retraining fires
                    automatically after synthetic data generation.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: 10 }}>
          <span className="material-symbols-rounded">lightbulb</span>
          Suggested Workflow
        </div>
        <div className="stat-foot" style={{ lineHeight: 1.7 }}>
          After drift-triggered synthetic data generation, validate the new samples on the
          Synthetic Data page, then enable Auto Retrain in Engine Parameters before the next
          ingestion run. Monitor accuracy delta in the Logs &amp; Artifacts page post-retrain.
        </div>
        <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
          <button className="btn" onClick={() => navigate("/synthetic-data")}>
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>auto_awesome_mosaic</span>
            View Synthetics
          </button>
          <button className="btn primary" onClick={() => navigate("/ingestion")}>
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>upload_file</span>
            Go to Ingestion
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: 10 }}>
          <span className="material-symbols-rounded">fact_check</span>
          Human Verification Queue
        </div>
        <div className="stat-foot" style={{ marginBottom: 16 }}>
          Samples with extremely low confidence or uncertain random defect predictions require expert validation before being used for GAN retraining.
        </div>

        <div className="grid-4" style={{ marginBottom: 16 }}>
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">verified</span>
              High Confidence
            </div>
            <div className="metric-value">{queueStats.high_confidence_samples ?? 0}</div>
            <div className="metric-foot">eligible for GAN</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">remove_circle</span>
              Medium Confidence
            </div>
            <div className="metric-value">{queueStats.medium_confidence_samples ?? 0}</div>
            <div className="metric-foot">excluded from retraining</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">pending_actions</span>
              Awaiting Review
            </div>
            <div className="metric-value">{queueStats.awaiting_expert_review ?? 0}</div>
            <div className="metric-foot">expert validation needed</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">
              <span className="material-symbols-rounded">task_alt</span>
              Human Verified
            </div>
            <div className="metric-value">{queueStats.human_verified_samples ?? 0}</div>
            <div className="metric-foot">added to GAN input</div>
          </div>
        </div>

        {queueError ? (
          <div className="advisory-banner" style={{ marginBottom: 16 }}>
            <span className="material-symbols-rounded">warning</span>
            <div>
              <div className="advisory-label">Queue Error</div>
              <div className="advisory-text">{queueError}</div>
            </div>
          </div>
        ) : null}

        {loadingQueue ? (
          <div className="stat-foot">Loading human verification queue...</div>
        ) : queueItems.length ? (
          <div style={{ overflowX: "auto" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: queueGridColumns,
                gap: 16,
                alignItems: "center",
                minWidth: 1320,
                marginBottom: 12,
                padding: "0 6px 10px",
                borderBottom: "1px solid var(--stroke)",
                color: "var(--muted)",
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              <div>Image Preview</div>
              <div>Inspection ID</div>
              <div>Model Prediction</div>
              <div>Confidence</div>
              <div>Reason For Review</div>
              <div>Expert Label</div>
              <div>Status</div>
              <div>Action</div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {queueItems.map((item) => {
                const currentLabel = draftLabels[item.review_id] ?? item.expert_label ?? "";
                const disabled = busyRow === item.review_id;
                return (
                  <div
                    key={item.review_id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: queueGridColumns,
                      gap: 16,
                      alignItems: "center",
                      minWidth: 1320,
                      border: "1px solid var(--stroke-major)",
                      borderRadius: "var(--r-lg)",
                      padding: "16px 18px",
                      background: "var(--bg-0)",
                    }}
                  >
                    <div>
                      <img
                        src={item.wafer_image}
                        alt={item.inspection_id}
                        style={{
                          width: 88,
                          height: 88,
                          objectFit: "cover",
                          borderRadius: "var(--r-md)",
                          border: "1px solid var(--stroke-major)",
                          background: "var(--panel)",
                        }}
                      />
                    </div>

                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{item.inspection_id}</div>
                      <div className="stat-foot" style={{ marginTop: 6 }}>{item.timestamp}</div>
                    </div>

                    <div style={{ textTransform: "capitalize", fontWeight: 600 }}>
                      {item.model_prediction}
                    </div>

                    <div>
                      <div style={{ fontWeight: 600 }}>{formatConfidence(item.confidence)}</div>
                      <div className="stat-foot" style={{ marginTop: 6 }}>
                        {item.review_reason || "Needs review"}
                      </div>
                    </div>

                    <div>
                      <span className={`chip ${item.review_reason === "Random Class Verification" ? "info" : "warn"}`}>
                        {item.review_reason || "Low Confidence"}
                      </span>
                    </div>

                    <div>
                      <select
                        value={currentLabel}
                        onChange={(event) => {
                          setDraftLabels((prev) => ({
                            ...prev,
                            [item.review_id]: event.target.value,
                          }));
                        }}
                        disabled={disabled}
                        style={{
                          width: "100%",
                          minHeight: 42,
                          background: "var(--panel)",
                          color: "var(--text)",
                          border: "1px solid var(--stroke-major)",
                          borderRadius: "var(--r-md)",
                          padding: "10px 12px",
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          outline: "none",
                        }}
                      >
                        <option value="">Select label</option>
                        {labelOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
                      <span className={`chip ${statusChipClass(item)}`}>
                        {statusLabel(item)}
                      </span>
                      {item.eligible_for_gan ? <span className="chip info">Eligible for GAN</span> : null}
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "stretch" }}>
                      <button
                        className="btn primary sm"
                        onClick={() => handleSubmitLabel(item)}
                        disabled={disabled || !currentLabel || item.verification_status}
                        style={{ width: "100%", justifyContent: "center" }}
                      >
                        <span className="material-symbols-rounded" style={{ fontSize: 14 }}>task_alt</span>
                        Submit Label
                      </button>
                      <button
                        className="btn sm"
                        onClick={() => handleMarkReviewed(item)}
                        disabled={disabled}
                        style={{ width: "100%", justifyContent: "center" }}
                      >
                        <span className="material-symbols-rounded" style={{ fontSize: 14 }}>visibility</span>
                        Mark Reviewed
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="advisory-banner">
            <span className="material-symbols-rounded">task_alt</span>
            <div>
              <div className="advisory-label">Queue Clear</div>
              <div className="advisory-text">
                No extremely low-confidence samples are waiting for expert validation.
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
