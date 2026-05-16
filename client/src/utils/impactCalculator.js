import {
  createDefaultImpactInputs,
  defaultEnergyProfile,
  defaultGridProfile,
} from "../data/impactSources.js";

export function waferAreaCm2(waferDiameterMm) {
  const radiusCm = waferDiameterMm / 20;
  return Math.PI * radiusCm * radiusCm;
}

export function energyKwhPerWafer(energyKwhPerCm2, waferDiameterMm) {
  return energyKwhPerCm2 * waferAreaCm2(waferDiameterMm);
}

function toNullableNumber(value) {
  if (value === "" || value === null || value === undefined) {
    return null;
  }

  const next = Number(value);
  return Number.isFinite(next) ? next : null;
}

export function sanitizeImpactInputs(rawInputs = {}) {
  const defaults = createDefaultImpactInputs();
  const next = { ...defaults, ...rawInputs };
  const batchWaferCount = Math.max(1, Number(next.batchWaferCount) || defaults.batchWaferCount);
  const affectedWafersDetected = Math.min(
    batchWaferCount,
    Math.max(0, Number(next.affectedWafersDetected) || 0)
  );

  return {
    batchId: String(next.batchId ?? "").trim(),
    batchWaferCount,
    affectedWafersDetected,
    treatmentRecoveryRatePct: Math.min(
      100,
      Math.max(0, Number(next.treatmentRecoveryRatePct) || 0)
    ),
    waferDiameterMm: Number(next.waferDiameterMm) === 200 ? 200 : 300,
    loadedCostPerWaferInr: Math.max(0, Number(next.loadedCostPerWaferInr) || 0),
    electricityTariffInrPerKwh: Math.max(0, Number(next.electricityTariffInrPerKwh) || 0),
    manualEnergyIntensityOverrideKwhPerWafer: toNullableNumber(
      next.manualEnergyIntensityOverrideKwhPerWafer
    ),
    manualGridFactorOverrideKgco2PerKwh: toNullableNumber(
      next.manualGridFactorOverrideKgco2PerKwh
    ),
  };
}

export function buildImpactResult({ inspection, impactInputs, sources = {} }) {
  if (!inspection) {
    return null;
  }

  const inputs = sanitizeImpactInputs(impactInputs);
  const energyProfile = sources.energyProfile ?? defaultEnergyProfile;
  const gridProfile = sources.gridProfile ?? defaultGridProfile;

  const sourceEnergyKwhPerWafer = energyKwhPerWafer(
    energyProfile.energyKwhPerCm2,
    inputs.waferDiameterMm
  );
  const appliedEnergyKwhPerWafer =
    inputs.manualEnergyIntensityOverrideKwhPerWafer ?? sourceEnergyKwhPerWafer;
  const appliedGridFactorKgco2PerKwh =
    inputs.manualGridFactorOverrideKgco2PerKwh ?? gridProfile.factorValueKgco2PerKwh;

  const untreatedLossWafers = inputs.affectedWafersDetected;
  const treatedLossWafers =
    untreatedLossWafers * (1 - inputs.treatmentRecoveryRatePct / 100);
  const avoidedScrapWafers = untreatedLossWafers - treatedLossWafers;

  const yieldBefore =
    (inputs.batchWaferCount - untreatedLossWafers) / inputs.batchWaferCount;
  const yieldAfter =
    (inputs.batchWaferCount - treatedLossWafers) / inputs.batchWaferCount;
  const yieldUpliftPp = (yieldAfter - yieldBefore) * 100;

  const energySavedKwh = avoidedScrapWafers * appliedEnergyKwhPerWafer;
  const carbonPreventedKgco2e = energySavedKwh * appliedGridFactorKgco2PerKwh;
  const scrapCostSavedInr = avoidedScrapWafers * inputs.loadedCostPerWaferInr;
  const energyCostSavedInr = energySavedKwh * inputs.electricityTariffInrPerKwh;
  const totalCostSavedInr = scrapCostSavedInr + energyCostSavedInr;

  return {
    inspectionId: inspection.inspection_id,
    batchId: inputs.batchId || inspection.inspection_id || "UNSPECIFIED-BATCH",
    timestamp: inspection.timestamp ?? new Date().toISOString(),
    defectClass: inspection.defect_class,
    inputParams: inputs,
    waferAreaCm2: waferAreaCm2(inputs.waferDiameterMm),
    untreatedLossWafers,
    treatedLossWafers,
    avoidedScrapWafers,
    yieldBefore,
    yieldAfter,
    yieldUpliftPp,
    sourceEnergyKwhPerCm2: energyProfile.energyKwhPerCm2,
    sourceEnergyKwhPerWafer,
    appliedEnergyKwhPerWafer,
    sourceGridFactorKgco2PerKwh: gridProfile.factorValueKgco2PerKwh,
    appliedGridFactorKgco2PerKwh,
    energySavedKwh,
    carbonPreventedKgco2e,
    scrapCostSavedInr,
    energyCostSavedInr,
    totalCostSavedInr,
    manualEnergyOverrideApplied:
      inputs.manualEnergyIntensityOverrideKwhPerWafer !== null,
    manualGridOverrideApplied: inputs.manualGridFactorOverrideKgco2PerKwh !== null,
    sources: {
      energyProfile,
      gridProfile,
    },
  };
}

export function appendImpactHistory(history = [], impactResult) {
  if (!impactResult) {
    return history;
  }

  return [...history.slice(-49), impactResult];
}

export function summarizeImpactHistory(history = []) {
  if (!history.length) {
    return {
      batchesAnalyzed: 0,
      energySavedKwh: 0,
      carbonPreventedKgco2e: 0,
      totalCostSavedInr: 0,
      avgYieldUpliftPp: 0,
    };
  }

  const batchesAnalyzed = history.length;
  const energySavedKwh = history.reduce((sum, item) => sum + item.energySavedKwh, 0);
  const carbonPreventedKgco2e = history.reduce(
    (sum, item) => sum + item.carbonPreventedKgco2e,
    0
  );
  const totalCostSavedInr = history.reduce((sum, item) => sum + item.totalCostSavedInr, 0);
  const avgYieldUpliftPp =
    history.reduce((sum, item) => sum + item.yieldUpliftPp, 0) / batchesAnalyzed;

  return {
    batchesAnalyzed,
    energySavedKwh,
    carbonPreventedKgco2e,
    totalCostSavedInr,
    avgYieldUpliftPp,
  };
}
