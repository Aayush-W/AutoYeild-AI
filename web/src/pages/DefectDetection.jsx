import { useInspection } from "../context/InspectionContext.jsx";

const defectDescriptions = {
  scratch: "Linear mechanical damage on wafer surface",
  particle: "Foreign material deposition causing contamination",
  crack: "Structural fracture or stress-induced cracking",
  clean: "No defect detected on wafer surface",
  normal: "No defect detected on wafer surface",
  random: "Scattered defect points across surface",
  local: "Localized defect cluster in a region",
  edge_ring: "Ring-shaped defects near wafer edge",
  center: "Defects concentrated near wafer center"
};

export default function DefectDetection() {
  const { inspection } = useInspection();
  const hasData = Boolean(inspection);
  const label = hasData ? inspection.defect_class : "Scratch";
  const normalizedLabel = label
    ?.toLowerCase()
    .replace(/[\s-]+/g, "_")
    .trim();
  const description =
    defectDescriptions[normalizedLabel] || "Defect description unavailable.";
  const severity = inspection?.reasoning?.severity_assessment || "Medium";

  return (
    <>
      <div>
        <div className="topbar-title">Defect Detection</div>
        <div className="stat-foot">ML classification results</div>
      </div>

      <div className="card" style={{ display: "flex", gap: 16, alignItems: "center" }}>
        <div className="tag">{hasData ? inspection.defect_class : "Scratch"}</div>
        <div className="stat-foot">
          Inspection ID: {hasData ? inspection.inspection_id : "INS-1770215724694"}
        </div>
        <div style={{ marginLeft: "auto", color: "var(--muted)" }}>
          {hasData ? inspection.timestamp : "2/4/2026, 8:05:24 PM"}
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h3>Original Wafer Image</h3>
          {hasData ? (
            <div className="image-frame">
              <img src={inspection.input_image} alt="Wafer" />
            </div>
          ) : (
            <div className="wafer mini-grid">Wafer</div>
          )}
        </div>
        <div className="card">
          <h3>Classification Result</h3>
          <div style={{ fontSize: 24, fontWeight: 700, color: "#f6b23a" }}>
            {label}
          </div>
          <div className="stat-foot">{description}</div>
          <div style={{ marginTop: 16 }}>
            <div className="stat-foot">Confidence Score</div>
            <div className="progress" style={{ width: "100%", marginTop: 6 }}>
              <span style={{ width: `${hasData ? Math.round(inspection.confidence * 100) : 96}%` }} />
            </div>
          </div>
          <div style={{ marginTop: 16, display: "flex", gap: 16 }}>
            <div>
              <div className="stat-foot">Severity</div>
              <div className="chip warn">{severity}</div>
            </div>
            <div>
              <div className="stat-foot">Inference Time</div>
              <div style={{ fontWeight: 600 }}>
                {hasData ? `${inspection.inference_time_ms} ms` : "47 ms"}
              </div>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <h3>Top Predictions</h3>
            <div className="timeline">
              {(hasData ? inspection.top_predictions : [
                { label: "Scratch", prob: 0.965 },
                { label: "Normal", prob: 0.036 },
                { label: "Particle", prob: 0.025 }
              ]).map((item, index) => (
                <div className="timeline-item" key={`${item.label}-${index}`}>
                  <div>{index + 1}. {item.label}</div>
                  <div className="progress">
                    <span style={{ width: `${Math.round(item.prob * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
