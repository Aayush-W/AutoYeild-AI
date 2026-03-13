import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { analyzeImage, getHistory, getMetrics } from "../api/client.js";
import { createDefaultImpactInputs, defaultEnergyProfile, defaultGridProfile } from "../data/impactSources.js";
import {
  appendImpactHistory,
  buildImpactResult,
  summarizeImpactHistory,
} from "../utils/impactCalculator.js";

const InspectionContext = createContext(null);

export function InspectionProvider({ children }) {
  const [inspection, setInspection] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [impactInputs, setImpactInputs] = useState(() => createDefaultImpactInputs());
  const [impactHistory, setImpactHistory] = useState([]);

  const impactSources = useMemo(
    () => ({
      energyProfile: defaultEnergyProfile,
      gridProfile: defaultGridProfile,
    }),
    []
  );

  const updateImpactInputs = useCallback((partialInputs) => {
    setImpactInputs((prev) => ({ ...prev, ...partialInputs }));
  }, []);

  const refreshDashboard = useCallback(async () => {
    try {
      const [historyData, metricsData] = await Promise.all([
        getHistory(),
        getMetrics()
      ]);
      setHistory(historyData);
      setMetrics(metricsData);
    } catch (err) {
      setError(err.message || "Failed to load dashboard data");
    }
  }, []);

  const runAnalysis = useCallback(async (file, options) => {
    setLoading(true);
    setError("");
    try {
      const result = await analyzeImage(file, options);
      const nextImpactResult = buildImpactResult({
        inspection: result,
        impactInputs,
        sources: impactSources,
      });

      setInspection(result);
      setImpactHistory((prev) => appendImpactHistory(prev, nextImpactResult));
      const [historyData, metricsData] = await Promise.all([
        getHistory(),
        getMetrics()
      ]);
      setHistory(historyData);
      setMetrics(metricsData);
      return result;
    } catch (err) {
      setError(err.message || "Analysis failed");
      throw err;
    } finally {
      setLoading(false);
    }
  }, [impactInputs, impactSources]);

  useEffect(() => {
    refreshDashboard();
  }, [refreshDashboard]);

  const impactResult = useMemo(
    () =>
      buildImpactResult({
        inspection,
        impactInputs,
        sources: impactSources,
      }),
    [impactInputs, impactSources, inspection]
  );

  const impactSummary = useMemo(
    () => summarizeImpactHistory(impactHistory),
    [impactHistory]
  );

  const value = useMemo(
    () => ({
      inspection,
      setInspection,
      runAnalysis,
      loading,
      error,
      history,
      metrics,
      refreshDashboard,
      impactInputs,
      updateImpactInputs,
      impactSources,
      impactResult,
      impactHistory,
      impactSummary,
    }),
    [
      error,
      history,
      impactHistory,
      impactInputs,
      impactResult,
      impactSources,
      impactSummary,
      inspection,
      loading,
      metrics,
      refreshDashboard,
      runAnalysis,
      updateImpactInputs,
    ]
  );

  return (
    <InspectionContext.Provider value={value}>
      {children}
    </InspectionContext.Provider>
  );
}

export function useInspection() {
  const context = useContext(InspectionContext);
  if (!context) {
    throw new Error("useInspection must be used within InspectionProvider");
  }
  return context;
}
