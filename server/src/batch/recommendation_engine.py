"""
recommendation_engine.py — Rule-based recommendation engine for batch results.
Optional GenAI enrichment when enable_genai=True and GEMINI_API_KEY is set.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

# ── Rule table ───────────────────────────────────────────────────────────────
_RULES: List[Dict[str, Any]] = [
    {
        "region": "edge_outer",
        "defect": "edge ring",
        "recommendation": "High edge-ring defects indicate deposition non-uniformity. Check tool calibration and edge exclusion margins.",
    },
    {
        "region": "edge_outer",
        "defect": "ring",
        "recommendation": "High ring defects at edge-outer zone. Check deposition uniformity or tool calibration.",
    },
    {
        "region": "edge_outer",
        "defect": "edge loc",
        "recommendation": "Edge localised defects detected. Inspect wafer handling robot and edge bevel cleanliness.",
    },
    {
        "region": "rim",
        "defect": "edge ring",
        "recommendation": "Rim zone edge-ring pattern — likely a wafer-edge exclusion or mechanical contact issue.",
    },
    {
        "region": "rim",
        "defect": "scratch",
        "recommendation": "Scratch defects at wafer rim. Inspect robotic handlers and carrier cassette contacts.",
    },
    {
        "region": "center",
        "defect": "random",
        "recommendation": "Random defects at wafer center. Check contamination sources such as process gas purity or chamber particles.",
    },
    {
        "region": "center",
        "defect": "center",
        "recommendation": "Center-zone defect cluster. Verify center-zone temperature uniformity and gas-flow symmetry.",
    },
    {
        "region": "mid",
        "defect": "donut",
        "recommendation": "Donut defect in mid-zone. Radial temperature gradient likely; review anneal ramp rates.",
    },
    {
        "region": "mid",
        "defect": "local",
        "recommendation": "Local defects in mid-zone. Correlated with localised contamination; review upstream filtration.",
    },
    {
        "region": "edge_inner",
        "defect": "near full",
        "recommendation": "Near-full coverage defects at inner-edge. Possible photoresist coating coverage issue.",
    },
]

_FALLBACK = (
    "Defect pattern detected — monitor process parameters and schedule targeted diagnostics."
)


def _match_rule(region: str, dominant_defect: str) -> str | None:
    region_lc = region.strip().lower()
    defect_lc = dominant_defect.strip().lower()
    for rule in _RULES:
        if rule["region"] == region_lc and rule["defect"] in defect_lc:
            return rule["recommendation"]
    return None


def generate_recommendations(
    region_stats: List[Dict[str, Any]],
    enable_genai: bool = False,
) -> List[Dict[str, Any]]:
    """
    Produce one recommendation per region in region_stats.

    Applies rule-based matching first; falls back to a generic recommendation
    when no rule matches. GenAI enrichment is attempted when enable_genai=True.
    """
    recommendations: List[Dict[str, Any]] = []

    for stat in region_stats:
        region = stat["region"]
        dominant = stat.get("dominant_defect", "unknown")
        density = stat.get("defect_density", 0.0)
        source = "rule"

        rec_text = _match_rule(region, dominant)
        if rec_text is None:
            rec_text = _FALLBACK
            source = "fallback"

        enriched = rec_text
        if enable_genai and density > 0.3:
            try:
                enriched = _enrich_with_genai(region, dominant, density, rec_text)
                source = "genai"
            except Exception:
                # Fail-safe: use rule text
                enriched = rec_text
                source = "rule_fallback"

        recommendations.append(
            {
                "region": region,
                "defect": dominant,
                "density": density,
                "recommendation": enriched,
                "source": source,
            }
        )

    return recommendations


def _enrich_with_genai(
    region: str, defect: str, density: float, base_rec: str
) -> str:
    """
    Optional GenAI enrichment via google-generativeai.
    Only called when density > 0.3 and GEMINI_API_KEY is present.
    """
    import google.generativeai as genai  # type: ignore

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = (
        f"You are a semiconductor process engineer. "
        f"A wafer inspection identified '{defect}' defects in the '{region}' zone "
        f"with a defect density of {density:.0%}. "
        f"Provide a concise (1–2 sentences) actionable recommendation. "
        f"Base recommendation: {base_rec}"
    )
    response = model.generate_content(prompt)
    return response.text.strip()
