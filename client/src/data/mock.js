export const trendBars = [
  40, 32, 45, 68, 55, 59, 62, 58, 44, 36, 60, 48,
  52, 70, 35, 46, 61, 57, 53, 49, 60, 55, 62, 58
];

export const inspections = [
  { id: 1, label: "Contamination", time: "8:12:27 PM", score: 92 },
  { id: 2, label: "Pattern Defect", time: "8:07:27 PM", score: 78 },
  { id: 3, label: "Normal", time: "8:02:27 PM", score: 88 },
  { id: 4, label: "Pattern Defect", time: "7:57:27 PM", score: 64 },
  { id: 5, label: "Pattern Defect", time: "7:52:27 PM", score: 70 }
];

export const alerts = [
  {
    id: 1,
    variant: "warn",
    title: "Confidence trending below threshold on Line 3",
    detail: "Investigation recommended",
    time: "8:07:27 PM"
  },
  {
    id: 2,
    variant: "info",
    title: "Scheduled maintenance reminder: Edge grinder calibration",
    detail: "Due within 24 hours",
    time: "8:02:27 PM"
  }
];
