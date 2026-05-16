/**
 * BatchWaferMap2D.jsx — 2D SVG wafer heat map for batch inspection results.
 * Renders a grid of coloured cells, one per image, mapped to spatial regions.
 */
import { useState } from "react";

const REGION_LABEL = {
  center: "Center",
  mid: "Mid",
  edge_inner: "Edge Inner",
  edge_outer: "Edge Outer",
  rim: "Rim",
};

export default function BatchWaferMap2D({ visualization }) {
  const [tooltip, setTooltip] = useState(null);

  if (!visualization) {
    return (
      <div className="batch-map-empty">
        <span className="material-symbols-rounded" style={{ fontSize: 40, opacity: 0.3 }}>bubble_chart</span>
        <p>No visualization data</p>
      </div>
    );
  }

  const { grid_points, grid_size, region_map, legend, total_images } = visualization;
  const cellSize = Math.max(8, Math.min(28, Math.floor(320 / (grid_size || 1))));
  const gap = 2;
  const svgSize = grid_size * (cellSize + gap) + gap;

  return (
    <div className="batch-wafer-2d">
      <div className="batch-wafer-2d-title">
        <span className="material-symbols-rounded">grid_on</span>
        Wafer Grid Map
      </div>

      {/* Background wafer circle */}
      <div className="batch-wafer-svg-wrap" style={{ width: svgSize + 40, height: svgSize + 40 }}>
        <svg
          width={svgSize + 40}
          height={svgSize + 40}
          style={{ overflow: "visible" }}
        >
          {/* Wafer circle background */}
          <ellipse
            cx={(svgSize + 40) / 2}
            cy={(svgSize + 40) / 2}
            rx={(svgSize + 40) / 2 - 2}
            ry={(svgSize + 40) / 2 - 2}
            fill="rgba(255,255,255,0.03)"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={1}
          />

          {/* Grid cells */}
          <g transform="translate(20, 20)">
            {grid_points.map((pt) => {
              const cx = pt.x * (cellSize + gap) + gap;
              const cy = pt.y * (cellSize + gap) + gap;
              return (
                <rect
                  key={pt.index}
                  x={cx}
                  y={cy}
                  width={cellSize}
                  height={cellSize}
                  rx={2}
                  fill={pt.color}
                  opacity={0.72 + pt.confidence * 0.28}
                  style={{ cursor: "pointer", transition: "opacity 0.15s" }}
                  onMouseEnter={(e) =>
                    setTooltip({
                      x: e.clientX,
                      y: e.clientY,
                      pt,
                    })
                  }
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            })}
          </g>
        </svg>

        {/* Region ring overlays (text labels) */}
        {region_map && region_map.map((r) => null)}
      </div>

      {/* Legend */}
      <div className="batch-wafer-legend">
        {legend &&
          legend.slice(0, 6).map((l) => (
            <div key={l.label} className="batch-legend-item">
              <div
                className="batch-legend-dot"
                style={{ background: l.color }}
              />
              <span>{l.label}</span>
            </div>
          ))}
      </div>

      {tooltip && (
        <div
          className="batch-wafer-tooltip"
          style={{
            position: "fixed",
            left: tooltip.x + 12,
            top: tooltip.y - 8,
            pointerEvents: "none",
            zIndex: 9999,
          }}
        >
          <div className="tooltip-label">{tooltip.pt.label}</div>
          <div className="tooltip-meta">
            Region: {REGION_LABEL[tooltip.pt.region] || tooltip.pt.region}
          </div>
          <div className="tooltip-meta">
            Confidence: {(tooltip.pt.confidence * 100).toFixed(1)}%
          </div>
          <div className="tooltip-meta">File: {tooltip.pt.filename}</div>
        </div>
      )}

      <div className="batch-wafer-count">
        {total_images} images · {grid_size}×{grid_size} grid
      </div>
    </div>
  );
}
