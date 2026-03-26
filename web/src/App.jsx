import { useCallback, useEffect, useRef, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import SystemOverview from "./pages/SystemOverview.jsx";
import ImageIngestion from "./pages/ImageIngestion.jsx";
import DefectDetection from "./pages/DefectDetection.jsx";
import Explainability from "./pages/Explainability.jsx";
import RootCause from "./pages/RootCause.jsx";
import DriftMonitoring from "./pages/DriftMonitoring.jsx";
import SyntheticData from "./pages/SyntheticData.jsx";
import AutoRetraining from "./pages/AutoRetraining.jsx";
import LogsArtifacts from "./pages/LogsArtifacts.jsx";
import BatchInspection from "./pages/BatchInspection.jsx";
import { InspectionProvider } from "./context/InspectionContext.jsx";

function AppRoutes() {
  const { pathname } = useLocation();
  const [overviewMode, setOverviewMode] = useState("frontpage");
  const [isModeSwitching, setIsModeSwitching] = useState(false);
  const overviewInitialized = useRef(false);
  const switchTimerRef = useRef(null);

  useEffect(() => {
    if (pathname !== "/overview" || overviewInitialized.current) {
      return;
    }
    overviewInitialized.current = true;
    setOverviewMode("frontpage");
  }, [pathname]);

  useEffect(
    () => () => {
      if (switchTimerRef.current) {
        clearTimeout(switchTimerRef.current);
      }
    },
    []
  );

  const handleSetOverviewMode = useCallback((nextMode) => {
    setOverviewMode((prev) => {
      const resolved = typeof nextMode === "function" ? nextMode(prev) : nextMode;
      if (resolved === prev) {
        return prev;
      }

      setIsModeSwitching(true);
      if (switchTimerRef.current) {
        clearTimeout(switchTimerRef.current);
      }
      switchTimerRef.current = setTimeout(() => {
        setIsModeSwitching(false);
      }, 320);

      return resolved;
    });
  }, []);

  return (
    <Layout
      overviewMode={overviewMode}
      setOverviewMode={handleSetOverviewMode}
      isModeSwitching={isModeSwitching}
    >
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route
          path="/overview"
          element={
            <SystemOverview
              overviewMode={overviewMode}
              setOverviewMode={handleSetOverviewMode}
              isModeSwitching={isModeSwitching}
            />
          }
        />
        <Route path="/ingestion" element={<ImageIngestion />} />
        <Route path="/defect-detection" element={<DefectDetection />} />
        <Route path="/explainability" element={<Explainability />} />
        <Route path="/root-cause" element={<RootCause />} />
        <Route path="/drift-monitoring" element={<DriftMonitoring />} />
        <Route path="/synthetic-data" element={<SyntheticData />} />
        <Route path="/auto-retraining" element={<AutoRetraining />} />
        <Route path="/logs" element={<LogsArtifacts />} />
        <Route path="/batch-inspection" element={<BatchInspection />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <InspectionProvider>
      <AppRoutes />
    </InspectionProvider>
  );
}
