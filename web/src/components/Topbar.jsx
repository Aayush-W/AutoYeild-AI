import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

const titleMap = {
  "/overview": "System Overview",
  "/ingestion": "Image Ingestion",
  "/defect-detection": "Defect Detection",
  "/explainability": "Explainability",
  "/root-cause": "Root Cause Analysis",
  "/drift-monitoring": "Drift Monitoring",
  "/synthetic-data": "Synthetic Data",
  "/auto-retraining": "Auto-Retraining",
  "/logs": "Logs & Artifacts"
};

export default function Topbar() {
  const location = useLocation();
  const title = titleMap[location.pathname] || "System Overview";
  const [now, setNow] = useState(
    new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    })
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        })
      );
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-title">{title}</div>
      <div className="topbar-right">
        <span>{now}</span>
        <span>Notifications</span>
        <span>Settings</span>
      </div>
    </header>
  );
}
