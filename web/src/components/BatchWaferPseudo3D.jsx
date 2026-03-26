/**
 * BatchWaferPseudo3D.jsx — Pseudo-3D wafer map using isometric bar projection.
 * No external dependencies — pure CSS/SVG transform illusion.
 */

const REGION_ORDER = ["center", "mid", "edge_inner", "edge_outer", "rim"];
const REGION_LABEL = {
  center: "Center",
  mid: "Mid Zone",
  edge_inner: "Edge Inner",
  edge_outer: "Edge Outer",
  rim: "Rim",
};

export default function BatchWaferPseudo3D({ regionStats }) {
  if (!regionStats || regionStats.length === 0) {
    return (
      <div className="batch-map-empty">
        <span className="material-symbols-rounded" style={{ fontSize: 40, opacity: 0.3 }}>
          stacked_bar_chart
        </span>
        <p>No region data</p>
      </div>
    );
  }

  const sorted = [...regionStats].sort(
    (a, b) =>
      REGION_ORDER.indexOf(a.region) - REGION_ORDER.indexOf(b.region)
  );
  const maxDensity = Math.max(...sorted.map((s) => s.defect_density), 0.01);

  const COLORS = {
    center:     "#6366f1",
    mid:        "#f59e0b",
    edge_inner: "#f97316",
    edge_outer: "#ef4444",
    rim:        "#dc2626",
  };

  const BAR_MAX_H = 120;
  const BAR_W = 44;
  const GAP = 18;
  const svgW = sorted.length * (BAR_W + GAP) + GAP;
  const svgH = BAR_MAX_H + 60;

  return (
    <div className="batch-wafer-3d">
      <div className="batch-wafer-2d-title">
        <span className="material-symbols-rounded">stacked_bar_chart</span>
        Defect Density by Region
      </div>

      <svg width={svgW} height={svgH} style={{ overflow: "visible" }}>
        {sorted.map((stat, i) => {
          const barH = Math.max(4, (stat.defect_density / maxDensity) * BAR_MAX_H);
          const x = GAP + i * (BAR_W + GAP);
          const y = svgH - 42 - barH;
          const color = COLORS[stat.region] || "#6b7280";

          return (
            <g key={stat.region}>
              {/* Shadow */}
              <rect
                x={x + 4}
                y={y + 4}
                width={BAR_W}
                height={barH}
                rx={4}
                fill="rgba(0,0,0,0.25)"
              />
              {/* Main bar */}
              <rect
                x={x}
                y={y}
                width={BAR_W}
                height={barH}
                rx={4}
                fill={color}
                opacity={0.88}
              />
              {/* Top highlight */}
              <rect
                x={x}
                y={y}
                width={BAR_W}
                height={6}
                rx={4}
                fill="rgba(255,255,255,0.25)"
              />
              {/* Density label */}
              <text
                x={x + BAR_W / 2}
                y={y - 6}
                textAnchor="middle"
                fill={color}
                fontSize={10}
                fontWeight={700}
                fontFamily="var(--font-mono, monospace)"
              >
                {(stat.defect_density * 100).toFixed(0)}%
              </text>
              {/* Region label */}
              <text
                x={x + BAR_W / 2}
                y={svgH - 24}
                textAnchor="middle"
                fill="rgba(255,255,255,0.55)"
                fontSize={9}
                fontFamily="var(--font-mono, monospace)"
              >
                {(REGION_LABEL[stat.region] || stat.region).toUpperCase()}
              </text>
              {/* Dominant defect */}
              <text
                x={x + BAR_W / 2}
                y={svgH - 10}
                textAnchor="middle"
                fill="rgba(255,255,255,0.35)"
                fontSize={8}
                fontFamily="var(--font-mono, monospace)"
              >
                {stat.dominant_defect}
              </text>
            </g>
          );
        })}
        {/* Baseline */}
        <line
          x1={0}
          y1={svgH - 42}
          x2={svgW}
          y2={svgH - 42}
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={1}
        />
      </svg>
    </div>
  );
}
