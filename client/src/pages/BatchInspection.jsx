import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { getBatchInspectionStatus, startBatchInspection } from "../api/client.js";
import "./batch-inspection-3d.css";

const WaferDigitalTwin3D = lazy(() => import("../components/WaferDigitalTwin3D.jsx"));

const POLL_INTERVAL_MS = 800;
const MAX_PREVIEW_ITEMS = 36;
const DEFECT_FREE_LABELS = new Set(["clean", "normal"]);
const PROCESS_STEPS = ["Uploading", "Processing", "Aggregating", "Rendering 3D Model"];

const REGION_LABEL = {
  center: "Center",
  mid: "Mid",
  edge_inner: "Edge Inner",
  edge_outer: "Edge Outer",
  rim: "Rim",
};

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function shortName(name, limit = 22) {
  if (!name) return "unknown";
  if (name.length <= limit) return name;
  return `${name.slice(0, limit - 1)}...`;
}

function stageFromState(phase, jobState) {
  if (phase === "done") return 3;
  if (phase !== "running" || !jobState) return 0;
  const total = Math.max(1, Number(jobState.total || 1));
  const processed = Number(jobState.processed || 0);
  const ratio = processed / total;
  if (ratio <= 0.01) return 0;
  if (ratio < 0.82) return 1;
  if (ratio < 1) return 2;
  return 3;
}

function severityTier(density) {
  const value = Number(density || 0);
  if (value >= 0.65) return "critical";
  if (value >= 0.4) return "high";
  if (value >= 0.2) return "moderate";
  return "low";
}

function severityColor(density) {
  const tier = severityTier(density);
  if (tier === "critical") return "#ef4444";
  if (tier === "high") return "#f97316";
  if (tier === "moderate") return "#eab308";
  return "#22c55e";
}

function regionColor(region) {
  const normalized = String(region || "").toLowerCase();
  const map = {
    center: "#34d399",
    mid: "#22d3ee",
    edge_inner: "#f59e0b",
    edge_outer: "#f97316",
    rim: "#ef4444",
  };
  return map[normalized] || "#94a3b8";
}

function normalizeLabel(label) {
  return String(label || "unknown").trim().toLowerCase();
}

function normalizeFilenameKey(name) {
  return String(name || "").split(/[\\/]/).pop().trim().toLowerCase();
}

function mapBatchError(err) {
  const status = err?.status;
  const message = String(err?.message || "");
  const lower = message.toLowerCase();
  if (lower.includes("failed to fetch") || lower.includes("networkerror")) {
    return "Cannot reach backend API on http://localhost:8000. Start backend with: uvicorn api.app:app --host 0.0.0.0 --port 8000";
  }
  if (status === 404 || lower.includes("not found")) {
    return "Batch API route not available on running backend. Restart backend from this repo.";
  }
  if (status === 400 && lower.includes("invalid zip archive")) {
    return "Invalid ZIP archive. Upload a valid .zip with wafer images.";
  }
  if (status === 400 && lower.includes("no valid image files")) {
    return "No valid image files detected. Use PNG/JPG/TIFF/BMP/WebP or ZIP containing them.";
  }
  return message || "Batch analysis failed.";
}

function BarChart({ data }) {
  if (!data.length) return <div className="batch3d-chart-empty">No defect data</div>;
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="batch3d-bar-chart">
      {data.map((item) => (
        <div key={item.label} className="batch3d-bar-row">
          <div className="batch3d-bar-meta">
            <span>{item.label}</span>
            <span>{item.value}</span>
          </div>
          <div className="batch3d-bar-track">
            <div className="batch3d-bar-fill" style={{ width: `${(item.value / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function PieChart({ data }) {
  const total = data.reduce((acc, item) => acc + item.value, 0);
  if (!total) return <div className="batch3d-chart-empty">No region distribution</div>;
  let running = 0;
  const gradient = data
    .map((item) => {
      const start = (running / total) * 360;
      running += item.value;
      const end = (running / total) * 360;
      return `${item.color} ${start}deg ${end}deg`;
    })
    .join(", ");

  return (
    <div className="batch3d-pie-wrap">
      <div className="batch3d-pie" style={{ background: `conic-gradient(${gradient})` }} />
      <div className="batch3d-pie-legend">
        {data.map((item) => (
          <div key={item.label} className="batch3d-pie-item">
            <span className="batch3d-pie-dot" style={{ background: item.color }} />
            <span>{item.label}</span>
            <strong>{pct(item.value / total)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendChart({ points }) {
  if (!points.length) return <div className="batch3d-chart-empty">No trend data</div>;
  const width = 420;
  const height = 160;
  const padding = 14;
  const values = points.map((p) => Number(p.value || 0));
  const max = Math.max(...values, 0.01);
  const path = points
    .map((point, index) => {
      const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((Number(point.value || 0) / max) * (height - padding * 2));
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="batch3d-trend-chart">
      <defs>
        <linearGradient id="trendStroke" x1="0%" x2="100%" y1="0%" y2="0%">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#ef4444" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width={width} height={height} fill="transparent" />
      <path d={path} fill="none" stroke="url(#trendStroke)" strokeWidth="3.2" />
      {points.map((point, index) => {
        const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
        const y = height - padding - ((Number(point.value || 0) / max) * (height - padding * 2));
        return <circle key={point.index} cx={x} cy={y} r="2.8" fill="#e2e8f0" />;
      })}
    </svg>
  );
}

function UploadPanel({ files, onChangeFiles, controls, onChangeControls, onRun, busy }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const previews = useMemo(
    () => files.filter((f) => f.type?.startsWith("image/")).slice(0, MAX_PREVIEW_ITEMS),
    [files]
  );
  const previewEntries = useMemo(
    () =>
      previews.map((file) => ({
        key: `${file.name}_${file.size}_${file.lastModified}`,
        name: file.name,
        url: URL.createObjectURL(file),
      })),
    [previews]
  );

  useEffect(
    () => () => {
      previewEntries.forEach((item) => URL.revokeObjectURL(item.url));
    },
    [previewEntries]
  );

  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      setDragging(false);
      const dropped = Array.from(event.dataTransfer.files || []);
      if (!dropped.length) return;
      onChangeFiles(dropped);
    },
    [onChangeFiles]
  );

  return (
    <section className="batch3d-panel">
      <div className="batch3d-panel-head">
        <h2>Batch Upload Panel</h2>
        <span>{files.length} files selected</span>
      </div>

      <div
        className={`batch3d-dropzone ${dragging ? "is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="batch3d-drop-icon">+</div>
        <div className="batch3d-drop-title">Drag and drop wafer images</div>
        <div className="batch3d-drop-subtitle">JPEG, PNG, TIFF, BMP, WEBP, ZIP</div>
        <button
          type="button"
          className="batch3d-secondary-btn"
          onClick={(event) => {
            event.stopPropagation();
            inputRef.current?.click();
          }}
        >
          Browse Batch
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.bmp,.tif,.tiff,.webp,.zip"
          multiple
          hidden
          onChange={(event) => onChangeFiles(Array.from(event.target.files || []))}
        />
      </div>

      <div className="batch3d-upload-controls">
        <label>
          Confidence Threshold
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={controls.confidenceThreshold}
            onChange={(event) => onChangeControls("confidenceThreshold", Number(event.target.value))}
          />
        </label>
        <label>
          Batch Size Limit
          <input
            type="number"
            min="1"
            max="256"
            step="1"
            value={controls.batchSize}
            onChange={(event) => onChangeControls("batchSize", Number(event.target.value))}
          />
        </label>
        <label>
          Region Segmentation
          <select
            value={controls.segmentationMode}
            onChange={(event) => onChangeControls("segmentationMode", event.target.value)}
          >
            <option value="auto">Auto</option>
            <option value="manual">Manual</option>
          </select>
        </label>
      </div>

      {previewEntries.length > 0 && (
        <div className="batch3d-preview-strip">
          {previewEntries.map((item) => (
            <div key={item.key} className="batch3d-preview-item">
              <img src={item.url} alt={item.name} />
              <span>{shortName(item.name, 16)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="batch3d-panel-actions">
        <button type="button" className="batch3d-primary-btn" disabled={busy || files.length === 0} onClick={onRun}>
          Run Batch Analysis
        </button>
      </div>
    </section>
  );
}

function ProcessingStatus({ phase, jobState }) {
  const active = stageFromState(phase, jobState);
  const total = Number(jobState?.total || 0);
  const processed = Number(jobState?.processed || 0);
  const progress = total > 0 ? Math.min(1, processed / total) : 0;

  return (
    <section className="batch3d-panel">
      <div className="batch3d-panel-head">
        <h2>Processing Pipeline</h2>
        <span>{phase === "done" ? "Completed" : phase === "running" ? "Running" : "Idle"}</span>
      </div>
      <div className="batch3d-progress-wrap">
        <div className="batch3d-progress-bar">
          <div className="batch3d-progress-fill" style={{ width: `${progress * 100}%` }} />
        </div>
        <div className="batch3d-progress-meta">
          <span>Processing {processed} / {total} images</span>
          <strong>{Math.round(progress * 100)}%</strong>
        </div>
      </div>
      <div className="batch3d-step-grid">
        {PROCESS_STEPS.map((step, index) => {
          const state =
            index < active ? "done" : index === active && phase !== "done" ? "active" : phase === "done" ? "done" : "pending";
          return (
            <div key={step} className={`batch3d-step ${state}`}>
              <span className="dot" />
              <span>{step}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function RegionAnalytics({ regionStats }) {
  return (
    <section className="batch3d-panel">
      <div className="batch3d-panel-head">
        <h2>Region Analytics</h2>
        <span>Spatial severity map</span>
      </div>
      <div className="batch3d-region-grid">
        {regionStats.map((stat) => (
          <article
            key={stat.region}
            className={`batch3d-region-card ${severityTier(stat.defect_density)}`}
            style={{ "--region-accent": severityColor(stat.defect_density) }}
          >
            <header>
              <h3>{REGION_LABEL[stat.region] || stat.region}</h3>
              <strong>{pct(stat.defect_density)}</strong>
            </header>
            <div className="batch3d-region-row">Dominant defect: <b>{stat.dominant_defect}</b></div>
            <div className="batch3d-region-row">Avg confidence: <b>{pct(stat.avg_confidence)}</b></div>
            <div className="batch3d-region-row">Images analyzed: <b>{stat.total}</b></div>
          </article>
        ))}
      </div>
    </section>
  );
}

function DefectCharts({ chartData }) {
  return (
    <section className="batch3d-panel">
      <div className="batch3d-panel-head">
        <h2>Defect Distribution Charts</h2>
        <span>Type, region, and progression</span>
      </div>
      <div className="batch3d-chart-grid">
        <article className="batch3d-chart-card">
          <h3>Defect Types vs Count</h3>
          <BarChart data={chartData.bar} />
        </article>
        <article className="batch3d-chart-card">
          <h3>Region Distribution</h3>
          <PieChart data={chartData.pie} />
        </article>
        <article className="batch3d-chart-card full">
          <h3>Batch Defect Evolution</h3>
          <TrendChart points={chartData.trend} />
        </article>
      </div>
    </section>
  );
}

function InsightPanel({ insights, recommendation, rootCause }) {
  return (
    <section className="batch3d-panel">
      <div className="batch3d-panel-head">
        <h2>AI Insights and Recommendations</h2>
        <span>Concise, technical, actionable</span>
      </div>
      <div className="batch3d-insight-grid">
        <article>
          <h3>Probable Root Cause</h3>
          <p>{rootCause}</p>
        </article>
        <article>
          <h3>Recommended Action</h3>
          <p>{recommendation}</p>
        </article>
        <article>
          <h3>Quality Summary</h3>
          <ul>
            <li>Defect rate: {pct(insights?.defect_rate)}</li>
            <li>Clean rate: {pct(insights?.clean_rate)}</li>
            <li>Worst region: {REGION_LABEL[insights?.worst_region] || insights?.worst_region || "N/A"}</li>
            <li>Confidence mean: {pct(insights?.confidence_mean)}</li>
          </ul>
        </article>
      </div>
    </section>
  );
}

function DigitalTwinSection({
  points,
  selectedCell,
  onSelectCell,
  mode,
  onChangeMode,
  cameraPreset,
  onChangeCamera,
  regionSamples,
  recommendations,
  combinedAnalysis,
}) {
  const recommendation = useMemo(() => {
    if (!selectedCell) return null;
    return recommendations.find((item) => item.region === selectedCell.region) || null;
  }, [recommendations, selectedCell]);

  return (
    <section className="batch3d-panel">
      <div className="batch3d-panel-head">
        <h2>3D Spatial Defect Intelligence</h2>
        <span>Digital Twin (WebGL)</span>
      </div>

      <div className="batch3d-mode-strip">
        <div className="batch3d-toggle-group">
          {[
            { key: "surface", label: "Surface Heatmap" },
            { key: "elevation", label: "Elevation Mode" },
            { key: "gradient", label: "Density Gradient" },
          ].map((item) => (
            <button
              type="button"
              key={item.key}
              className={mode === item.key ? "active" : ""}
              onClick={() => onChangeMode(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="batch3d-toggle-group">
          {[
            { key: "top", label: "Top" },
            { key: "isometric", label: "Isometric" },
            { key: "side", label: "Side" },
          ].map((item) => (
            <button
              type="button"
              key={item.key}
              className={cameraPreset === item.key ? "active" : ""}
              onClick={() => onChangeCamera(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="batch3d-digital-twin-layout">
        <div className="batch3d-canvas-shell">
          <Suspense fallback={<div className="batch3d-canvas-loading">Initializing 3D renderer...</div>}>
            <WaferDigitalTwin3D
              points={points}
              mode={mode}
              cameraPreset={cameraPreset}
              selectedCell={selectedCell}
              onSelectCell={onSelectCell}
              combinedAnalysis={combinedAnalysis}
            />
          </Suspense>
        </div>
        <aside className="batch3d-detail-panel">
          <h3>Selected Die Intelligence</h3>
          {selectedCell ? (
            <>
              {(selectedCell.image_data_uri || selectedCell.heatmap_image_data_uri) && (
                <div className="batch3d-selected-image-grid">
                  {selectedCell.image_data_uri && (
                    <div className="batch3d-selected-image">
                      <img src={selectedCell.image_data_uri} alt={selectedCell.filename || "selected die"} />
                      <span>Source</span>
                    </div>
                  )}
                  {selectedCell.heatmap_image_data_uri && (
                    <div className="batch3d-selected-image">
                      <img
                        src={selectedCell.heatmap_image_data_uri}
                        alt={`${selectedCell.filename || "selected die"} heatmap`}
                      />
                      <span>Heatmap</span>
                    </div>
                  )}
                </div>
              )}
              <div className="batch3d-detail-row">Region <strong>{REGION_LABEL[selectedCell.region] || selectedCell.region}</strong></div>
              <div className="batch3d-detail-row">Defect <strong>{selectedCell.label}</strong></div>
              <div className="batch3d-detail-row">Confidence <strong>{pct(selectedCell.confidence)}</strong></div>
              <div className="batch3d-detail-row">Density <strong>{pct(selectedCell.z || selectedCell.density)}</strong></div>
              <div className="batch3d-detail-row">File <strong>{shortName(selectedCell.filename || "unknown", 28)}</strong></div>
              <div className="batch3d-detail-block">
                <h4>Region Samples</h4>
                <div className="batch3d-sample-grid">
                  {regionSamples.map((item) => (
                    <div key={`${selectedCell.region}_${item.index}`} className="batch3d-sample-item">
                      {item.image_data_uri ? (
                        <img src={item.image_data_uri} alt={item.filename} />
                      ) : (
                        <div className="batch3d-sample-placeholder">No Preview</div>
                      )}
                      {item.heatmap_image_data_uri ? (
                        <img
                          src={item.heatmap_image_data_uri}
                          alt={`${item.filename} heatmap`}
                          className="batch3d-sample-heatmap"
                        />
                      ) : null}
                      <span>{shortName(item.filename, 16)}</span>
                    </div>
                  ))}
                  {!regionSamples.length && <p className="batch3d-muted">No samples for region</p>}
                </div>
              </div>
              <div className="batch3d-detail-block">
                <h4>Recommended Action</h4>
                <p>{recommendation?.recommendation || "Monitor process and run additional diagnostics for this region."}</p>
              </div>
              {combinedAnalysis?.grid_image && (
                <div className="batch3d-detail-block">
                  <h4>Composite Grid</h4>
                  <div className="batch3d-composite-grid">
                    <img src={combinedAnalysis.grid_image} alt="Composite uploaded image grid" />
                    {combinedAnalysis.grid_heatmap_image && (
                      <img src={combinedAnalysis.grid_heatmap_image} alt="Composite grid heatmap" />
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="batch3d-muted">Click a die node on the wafer to inspect detailed diagnostics.</p>
          )}
        </aside>
      </div>
    </section>
  );
}

export default function BatchInspection() {
  const [files, setFiles] = useState([]);
  const [phase, setPhase] = useState("upload");
  const [jobState, setJobState] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);
  const [cameraPreset, setCameraPreset] = useState("isometric");
  const [heatmapMode, setHeatmapMode] = useState("surface");
  const [controls, setControls] = useState({
    confidenceThreshold: 0.45,
    batchSize: 120,
    segmentationMode: "auto",
  });

  const pollRef = useRef(null);
  const pollInFlightRef = useRef(false);
  const activeJobRef = useRef(null);

  const localPreviewEntries = useMemo(
    () =>
      files
        .filter((file) => file.type?.startsWith("image/"))
        .map((file) => ({
          key: `${file.name}_${file.size}_${file.lastModified}`,
          filename: file.name,
          url: URL.createObjectURL(file),
        })),
    [files]
  );

  useEffect(
    () => () => {
      localPreviewEntries.forEach((entry) => URL.revokeObjectURL(entry.url));
    },
    [localPreviewEntries]
  );

  const localPreviewByFilename = useMemo(() => {
    const map = {};
    localPreviewEntries.forEach((entry) => {
      const key = normalizeFilenameKey(entry.filename);
      if (!key || map[key]) return;
      map[key] = entry.url;
    });
    return map;
  }, [localPreviewEntries]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    pollInFlightRef.current = false;
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const visualizationPointsRaw =
    result?.spatial_points?.length
      ? result.spatial_points
      : (result?.visualization?.grid_points || []);
  const visualizationPoints = useMemo(
    () =>
      visualizationPointsRaw.map((point) => {
        const key = normalizeFilenameKey(point.filename);
        const fallbackPreview = localPreviewByFilename[key];
        if (point.image_data_uri || !fallbackPreview) return point;
        return {
          ...point,
          image_data_uri: fallbackPreview,
        };
      }),
    [localPreviewByFilename, visualizationPointsRaw]
  );
  const regionStats = result?.region_stats || [];
  const recommendations = result?.recommendations || [];
  const individualResults = result?.individual_results || [];

  useEffect(() => {
    if (!visualizationPoints.length) {
      setSelectedCell(null);
      return;
    }
    const hotspot = [...visualizationPoints].sort((a, b) => Number(b.z || 0) - Number(a.z || 0))[0];
    setSelectedCell(hotspot || null);
  }, [result, visualizationPoints]);

  const chartData = useMemo(() => {
    const labelCounts = {};
    const trend = [];
    let defectCounter = 0;

    individualResults
      .filter((item) => item && normalizeLabel(item.label) !== "error")
      .sort((a, b) => Number(a.index || 0) - Number(b.index || 0))
      .forEach((item, index) => {
        const label = normalizeLabel(item.label);
        labelCounts[label] = (labelCounts[label] || 0) + 1;
        if (!DEFECT_FREE_LABELS.has(label)) {
          defectCounter += 1;
        }
        trend.push({
          index,
          value: defectCounter / (index + 1),
        });
      });

    const bar = Object.entries(labelCounts)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);

    const pie = regionStats.map((region) => ({
      label: REGION_LABEL[region.region] || region.region,
      value: Number(region.total || 0),
      color: regionColor(region.region),
    }));

    return { bar, pie, trend };
  }, [individualResults, regionStats]);

  const rootCauseSummary = useMemo(() => {
    const worstRegion = REGION_LABEL[result?.insights?.worst_region] || result?.insights?.worst_region || "wafer edge";
    const dominant = regionStats.find((item) => item.region === result?.insights?.worst_region)?.dominant_defect || "mixed defects";
    if (dominant.toLowerCase().includes("ring")) {
      return `Spatial concentration indicates ${dominant} in ${worstRegion}. This pattern is consistent with edge-process non-uniformity, likely from chamber drift or deposition imbalance.`;
    }
    return `Defect signature is concentrated in ${worstRegion} with dominant class ${dominant}. Pattern suggests localized process variation and potential tool-zone instability.`;
  }, [result, regionStats]);

  const recommendationSummary = useMemo(() => {
    if (recommendations.length) {
      return recommendations[0].recommendation;
    }
    return "Increase inspection cadence, recalibrate edge process parameters, and run chamber qualification lot before next production batch.";
  }, [recommendations]);

  const regionSamples = useMemo(() => {
    if (!selectedCell) return [];
    return visualizationPoints
      .filter((item) => item.region === selectedCell.region)
      .slice(0, 6)
      .map((item) => ({
        index: item.index,
        filename: item.filename,
        image_data_uri: item.image_data_uri,
        heatmap_image_data_uri: item.heatmap_image_data_uri,
      }));
  }, [selectedCell, visualizationPoints]);

  const startPolling = useCallback(
    (jobId) => {
      stopPolling();
      activeJobRef.current = jobId;

      const pollOnce = async () => {
        if (pollInFlightRef.current) return;
        pollInFlightRef.current = true;
        try {
          const state = await getBatchInspectionStatus(jobId);
          if (activeJobRef.current !== jobId) return;
          setJobState(state);
          if (state.status === "completed") {
            stopPolling();
            setResult(state.result);
            setPhase("done");
            setError(null);
          } else if (state.status === "failed") {
            stopPolling();
            setError(state.error || "Batch processing failed.");
            setPhase("error");
          } else {
            setPhase("running");
          }
        } catch (pollError) {
          stopPolling();
          setError(mapBatchError(pollError));
          setPhase("error");
        } finally {
          pollInFlightRef.current = false;
        }
      };

      pollOnce();
      pollRef.current = setInterval(pollOnce, POLL_INTERVAL_MS);
    },
    [stopPolling]
  );

  const handleChangeControl = useCallback((key, value) => {
    setControls((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleRun = useCallback(async () => {
    if (!files.length) return;
    if (files.length > controls.batchSize) {
      setError(`Selected ${files.length} files, exceeding batch size limit ${controls.batchSize}.`);
      return;
    }

    setError(null);
    setResult(null);
    setPhase("running");
    stopPolling();

    const form = new FormData();
    files
      .filter((file) => !file.name.toLowerCase().endsWith(".zip"))
      .forEach((file) => form.append("images", file));
    files
      .filter((file) => file.name.toLowerCase().endsWith(".zip"))
      .forEach((file) => form.append("archive", file));

    form.append("include_visualization", "true");
    form.append("enable_genai", "false");
    form.append("confidence_threshold", String(controls.confidenceThreshold));
    form.append("batch_size", String(controls.batchSize));
    form.append("region_segmentation_mode", controls.segmentationMode);

    try {
      const started = await startBatchInspection(form);
      setJobState({
        job_id: started.job_id,
        status: started.status,
        total: started.total,
        processed: 0,
        failed: 0,
      });
      startPolling(started.job_id);
    } catch (startError) {
      setError(mapBatchError(startError));
      setPhase("error");
    }
  }, [controls, files, startPolling, stopPolling]);

  const handleReset = useCallback(() => {
    stopPolling();
    activeJobRef.current = null;
    setFiles([]);
    setPhase("upload");
    setJobState(null);
    setResult(null);
    setSelectedCell(null);
    setError(null);
  }, [stopPolling]);

  return (
    <div className="batch3d-page">
      <header className="batch3d-header">
        <div>
          <p className="batch3d-kicker">AutoYield-AI Semiconductor Digital Twin</p>
          <h1>Batch Inspection with 3D Spatial Defect Intelligence</h1>
          <p className="batch3d-sub">
            AI-powered wafer batch analysis with immersive 3D spatial mapping, region diagnostics, and actionable fab recommendations.
          </p>
        </div>
        <div className="batch3d-header-actions">
          <button type="button" className="batch3d-secondary-btn" onClick={handleReset}>
            New Batch
          </button>
        </div>
      </header>

      {error && <div className="batch3d-error-banner">{error}</div>}

      <UploadPanel
        files={files}
        onChangeFiles={setFiles}
        controls={controls}
        onChangeControls={handleChangeControl}
        onRun={handleRun}
        busy={phase === "running"}
      />

      {(phase === "running" || phase === "done") && (
        <ProcessingStatus phase={phase} jobState={jobState} />
      )}

      {phase === "done" && result && (
        <>
          <DigitalTwinSection
            points={visualizationPoints}
            selectedCell={selectedCell}
            onSelectCell={setSelectedCell}
            mode={heatmapMode}
            onChangeMode={setHeatmapMode}
            cameraPreset={cameraPreset}
            onChangeCamera={setCameraPreset}
            regionSamples={regionSamples}
            recommendations={recommendations}
            combinedAnalysis={result.combined_analysis}
          />
          <RegionAnalytics regionStats={regionStats} />
          <DefectCharts chartData={chartData} />
          <InsightPanel
            insights={result.insights}
            recommendation={recommendationSummary}
            rootCause={rootCauseSummary}
          />
        </>
      )}
    </div>
  );
}
