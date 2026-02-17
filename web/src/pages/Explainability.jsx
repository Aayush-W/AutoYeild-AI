import { useState } from "react";
import { useInspection } from "../context/InspectionContext.jsx";

export default function Explainability() {
  const { inspection } = useInspection();
  const hasData = Boolean(inspection);
  const [showOverlay, setShowOverlay] = useState(true);
  const [sideBySide, setSideBySide] = useState(false);
  const [opacity, setOpacity] = useState(0.7);

  return (
    <>
      <div>
        <div className="topbar-title">Explainability</div>
        <div className="stat-foot">Grad-CAM visualization</div>
      </div>

      <div className="card">
        <h3>Visualization Controls</h3>
        <div className="toggle-row">
          <div>Show Heatmap Overlay</div>
          <input
            type="checkbox"
            checked={showOverlay}
            onChange={(event) => setShowOverlay(event.target.checked)}
          />
          <div>Side-by-Side Comparison</div>
          <input
            type="checkbox"
            checked={sideBySide}
            onChange={(event) => setSideBySide(event.target.checked)}
          />
          <div>Opacity</div>
          <input
            type="range"
            min="0"
            max="100"
            value={Math.round(opacity * 100)}
            onChange={(event) => setOpacity(Number(event.target.value) / 100)}
          />
          <div>{Math.round(opacity * 100)}%</div>
        </div>
      </div>

      <div className={sideBySide ? "grid-2" : ""}>
        <div className="card">
          <h3>Grad-CAM Visualization</h3>
          {hasData ? (
            showOverlay ? (
              <div className="overlay-container">
                <img src={inspection.input_image} alt="Original" />
                <img
                  src={inspection.heatmap_image}
                  alt="Grad-CAM"
                  className="overlay-heatmap"
                  style={{ opacity }}
                />
              </div>
            ) : (
              <div className="image-frame">
                <img src={inspection.heatmap_image} alt="Grad-CAM" />
              </div>
            )
          ) : (
            <div className="wafer mini-grid">Visualization</div>
          )}
          <div style={{ marginTop: 12 }} className="stat-foot">
            Focus region: Quadrant NE, Max activation: 0.94
          </div>
        </div>
        {sideBySide ? (
          <div className="card">
            <h3>Compare</h3>
            {hasData ? (
              <div className="image-frame">
                <img src={inspection.input_image} alt="Original" />
              </div>
            ) : (
              <div className="wafer mini-grid">Original</div>
            )}
          </div>
        ) : null}
      </div>
    </>
  );
}
