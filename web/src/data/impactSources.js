export const defaultEnergyProfile = {
  key: "hu_chuah_taiwan_2003",
  name: "Hu and Chuah Semiconductor Fab Average",
  sourceName: "Hu, S. C. and Chuah, Y. K.",
  sourceTitle: "Power consumption of semiconductor fabs in Taiwan",
  sourceUrl: "https://ntut.elsevierpure.com/en/publications/power-consumption-of-semiconductor-fabs-in-taiwan",
  journalUrl: "https://doi.org/10.1016/S0360-5442(03)00008-2",
  publicationYear: 2003,
  metricName: "Average power consumption per unit product (wafer) area",
  energyKwhPerCm2: 1.432,
  notes:
    "Average power consumption reported as 1.432 kWh/cm2 of wafer area across nine representative semiconductor fabs in Taiwan.",
};

export const defaultGridProfile = {
  key: "india_official",
  name: "India Official Grid Carbon Intensity",
  sourceName: "Central Electricity Authority",
  sourceTitle: "CO2 Baseline Database for the Indian Power Sector, User Guide Version 19.0",
  sourceUrl: "https://cea.nic.in/wp-content/uploads/baseline/2024/04/User_Guide__Version_19.0.pdf",
  landingUrl: "https://cea.nic.in/cdm-co2-baseline-database/?lang=en",
  reportVersion: "19.0",
  publicationYear: 2024,
  dataVintage: "FY 2022-23",
  factorType: "weighted_average",
  factorValueKgco2PerKwh: 0.823,
  notes:
    "Weighted-average emission rate used as the default grid intensity for avoided fab electricity consumption.",
};

export function createDefaultImpactInputs() {
  return {
    batchId: "",
    batchWaferCount: 25,
    affectedWafersDetected: 1,
    treatmentRecoveryRatePct: 75,
    waferDiameterMm: 300,
    loadedCostPerWaferInr: 0,
    electricityTariffInrPerKwh: 0,
    manualEnergyIntensityOverrideKwhPerWafer: "",
    manualGridFactorOverrideKgco2PerKwh: "",
  };
}
