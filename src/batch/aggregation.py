"""
aggregation.py — Batch result aggregation engine.
Computes per-region stats, batch-level insights, and prepares visualization data.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Dict, List

CLEAN_LABELS = {"clean", "normal"}


def _is_defect(label: str) -> bool:
    return label.strip().lower() not in CLEAN_LABELS


def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate a list of per-image inference results into region stats + batch insights.

    Each result dict must have: index, filename, region, label, confidence, x, y.
    """
    region_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        region_buckets[r["region"]].append(r)

    region_stats: List[Dict[str, Any]] = []
    for region, items in region_buckets.items():
        total = len(items)
        label_counts: Dict[str, int] = defaultdict(int)
        for item in items:
            label_counts[item["label"]] += 1

        dominant_defect = max(label_counts, key=label_counts.__getitem__)
        defect_count = sum(
            cnt for lbl, cnt in label_counts.items() if _is_defect(lbl)
        )
        defect_density = round(defect_count / total, 4) if total else 0.0
        confidences = [item["confidence"] for item in items]
        avg_confidence = round(statistics.mean(confidences), 4) if confidences else 0.0

        region_stats.append(
            {
                "region": region,
                "total": total,
                "label_counts": dict(label_counts),
                "dominant_defect": dominant_defect,
                "defect_density": defect_density,
                "avg_confidence": avg_confidence,
            }
        )

    # Sort by canonical region order for consistent display
    region_order = ["center", "mid", "edge_inner", "edge_outer", "rim"]
    region_stats.sort(
        key=lambda s: region_order.index(s["region"])
        if s["region"] in region_order
        else 99
    )

    # Batch-level insights
    total_images = len(results)
    all_confidences = [r["confidence"] for r in results]
    defect_results = [r for r in results if _is_defect(r["label"])]
    defect_rate = round(len(defect_results) / total_images, 4) if total_images else 0.0
    clean_rate = round(1.0 - defect_rate, 4) if total_images else 0.0

    conf_mean = round(statistics.mean(all_confidences), 4) if all_confidences else 0.0
    conf_std = (
        round(statistics.stdev(all_confidences), 4) if len(all_confidences) > 1 else 0.0
    )
    conf_min = round(min(all_confidences), 4) if all_confidences else 0.0
    conf_max = round(max(all_confidences), 4) if all_confidences else 0.0

    # Worst region: highest defect density, tie-break by lower avg_confidence
    worst_region = None
    if region_stats:
        worst = max(
            region_stats,
            key=lambda s: (s["defect_density"], -s["avg_confidence"]),
        )
        worst_region = worst["region"]

    insights = {
        "total_images": total_images,
        "clean_rate": clean_rate,
        "defect_rate": defect_rate,
        "confidence_mean": conf_mean,
        "confidence_std": conf_std,
        "confidence_min": conf_min,
        "confidence_max": conf_max,
        "worst_region": worst_region,
    }

    return {"region_stats": region_stats, "insights": insights}
