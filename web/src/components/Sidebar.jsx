import { NavLink } from "react-router-dom";

const navGroups = [
  {
    label: "Analytics",
    items: [
      { path: "/overview", icon: "dashboard", label: "System Overview" },
      { path: "/ingestion", icon: "upload_file", label: "Image Ingestion" },
      { path: "/defect-detection", icon: "analytics", label: "Defect Detection" },
      { path: "/explainability", icon: "visibility", label: "Explainability" },
      { path: "/root-cause", icon: "manage_search", label: "Root Cause" },
    ],
  },
  {
    label: "Autonomy",
    items: [
      { path: "/drift-monitoring", icon: "monitor_heart", label: "Drift Monitoring" },
      { path: "/synthetic-data", icon: "auto_fix_high", label: "Synthetic Data" },
      { path: "/auto-retraining", icon: "model_training", label: "Auto-Retraining" },
    ],
  },
  {
    label: "System",
    items: [
      { path: "/logs", icon: "history", label: "Logs & Artifacts" },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="brand">
        <div className="brand-logo">AY</div>
        <div className="brand-text">
          <h1>AutoYield</h1>
          <span>Semiconductor AI</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="nav">
        {navGroups.map((group) => (
          <div key={group.label} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <div className="nav-section-label">{group.label}</div>
            {group.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
              >
                <span className="material-symbols-rounded">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-avatar">AV</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">A. Vance</div>
            <div className="sidebar-user-role">Lead Engineer</div>
          </div>
        </div>
        <div className="status-pill">System Online</div>
        <div style={{ fontSize: 10, color: "var(--muted)" }}>Operator ID: 8821</div>
      </div>
    </aside>
  );
}
