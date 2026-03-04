"""
Root-cause analysis agent for wafer defect classification.

Key fixes:
- normalize_class() maps raw model labels (e.g. "Edge ring") to canonical
  snake_case keys before any rule lookup or GenAI prompt, eliminating the
  "unknown category" fallback for valid defects.
- Expanded output schema: risk_level, immediate_containment,
  validation_steps, owner_eta fields added (GenAI action-planner output).
- Fallback rules also produce the full structured schema so the API response
  is consistent whether or not a Gemini API key is present.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from src.utils.ontology import normalize_class


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confidence_level(confidence: float) -> str:
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.4:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Fallback rule base (offline / no API key)
# ---------------------------------------------------------------------------

def _fallback_rules(canonical_class: str, confidence: float) -> Dict[str, Any]:
    confidence_level = _confidence_level(confidence)

    defect_knowledge: Dict[str, Dict[str, str]] = {
        "center": {
            "pattern_reasoning": (
                "The defect pattern is concentrated near the wafer center, "
                "which typically correlates with non-uniform thermal or pressure conditions "
                "during central process phases."
            ),
            "cause": (
                "Instability in center-zone temperature or chamber pressure "
                "during deposition or etching steps."
            ),
            "action": (
                "Review thermal uniformity maps, recalibrate center-zone pressure control, "
                "and inspect recent process drift logs."
            ),
            "severity": "Medium",
            "containment": "Quarantine affected lot, run thermal profile diagnostic.",
            "validation": "Confirm center-zone uniformity via test wafer run.",
            "owner_eta": "Process Engineer — within 4 hours.",
        },
        "edge_ring": {
            "pattern_reasoning": (
                "Defects forming a ring near the wafer edge often indicate mechanical or alignment-related issues, "
                "especially during polishing or edge exclusion steps."
            ),
            "cause": "Wafer misalignment, edge over-polishing, or uneven edge pressure application.",
            "action": (
                "Verify wafer centering calibration, inspect edge exclusion parameters, "
                "and check polishing pad wear."
            ),
            "severity": "High",
            "containment": "Stop CMP tool run, escalate to equipment team.",
            "validation": "Re-run edge scan on next lot to confirm resolution.",
            "owner_eta": "Equipment Engineer — within 2 hours.",
        },
        "edge_loc": {
            "pattern_reasoning": (
                "Localized edge defects suggest a fixed-position contamination source or "
                "a tool-specific edge-exclusion misconfiguration."
            ),
            "cause": "Fixed contamination source at edge or asymmetric edge exclusion ring.",
            "action": "Inspect and clean edge exclusion ring; check notch alignment.",
            "severity": "Medium",
            "containment": "Hold lot pending edge exclusion parameter review.",
            "validation": "Run particle scan post-clean to confirm elimination.",
            "owner_eta": "Process Engineer — within 4 hours.",
        },
        "local": {
            "pattern_reasoning": (
                "Localized defect clusters suggest isolated contamination or transient process disturbances "
                "affecting a small wafer region."
            ),
            "cause": "Localized particle contamination or brief chamber instability.",
            "action": "Inspect recent chamber cleaning cycles and analyze tool logs for localized anomalies.",
            "severity": "Medium",
            "containment": "Mark affected dice, continue lot under enhanced monitoring.",
            "validation": "Verify particle counts post-chamber clean.",
            "owner_eta": "Tool Owner — within 6 hours.",
        },
        "scratch": {
            "pattern_reasoning": (
                "Linear or directional defect patterns are characteristic of mechanical contact "
                "during wafer handling or transport."
            ),
            "cause": "Physical contact from handling equipment or misaligned wafer transport mechanisms.",
            "action": "Audit wafer handling robots, cassette alignment, and transport paths.",
            "severity": "High",
            "containment": "Scrap affected wafers if scratch crosses active area; isolate handler.",
            "validation": "Inspect next 5 wafers from same handler slot.",
            "owner_eta": "FA Engineer — within 1 hour.",
        },
        "random": {
            "pattern_reasoning": (
                "Scattered, non-uniform defects across the wafer are often associated with airborne particles "
                "or sporadic contamination events."
            ),
            "cause": "Random particle deposition from cleanroom airflow disturbances or filter degradation.",
            "action": "Review cleanroom airflow data and particle counter logs.",
            "severity": "Low",
            "containment": "No immediate hold required; increase inline monitoring frequency.",
            "validation": "Check cleanroom particle counter trend for the past 24 hours.",
            "owner_eta": "Facilities Engineer — within 8 hours.",
        },
        "donut": {
            "pattern_reasoning": (
                "Donut-shaped defect ring at intermediate radius often indicates spin-coat or "
                "bake non-uniformity."
            ),
            "cause": "Resist spin-coat speed deviation or hotplate temperature non-uniformity.",
            "action": "Recalibrate spin-coater and verify hotplate temperature profile.",
            "severity": "Medium",
            "containment": "Hold affected photo lot; rework if within spec window.",
            "validation": "Run coat uniformity test wafer and verify CD variation < 2%.",
            "owner_eta": "Photo Engineer — within 4 hours.",
        },
        "near_full": {
            "pattern_reasoning": (
                "Defects covering most of the wafer surface indicate a systemic process failure "
                "such as complete etch stop, coat failure, or contaminated chemistry."
            ),
            "cause": "Systemic process failure — contaminated bath, chemistry exhaustion, or equipment crash.",
            "action": "Stop production, replace chemistry, and perform full tool qualification.",
            "severity": "Critical",
            "containment": "STOP LOT. Quarantine entire process batch. Notify shift supervisor immediately.",
            "validation": "Full re-qualification run required before production restart.",
            "owner_eta": "Shift Supervisor — IMMEDIATELY.",
        },
        "none": {
            "pattern_reasoning": "No significant defect patterns were detected across the wafer surface.",
            "cause": "Wafer appears within normal process limits.",
            "action": "No corrective action required. Continue routine monitoring.",
            "severity": "None",
            "containment": "N/A",
            "validation": "Continue standard SPC monitoring.",
            "owner_eta": "N/A",
        },
        "clean": {
            "pattern_reasoning": "No significant defect patterns were detected across the wafer surface.",
            "cause": "Wafer appears within normal process limits.",
            "action": "No corrective action required. Continue routine monitoring.",
            "severity": "None",
            "containment": "N/A",
            "validation": "Continue standard SPC monitoring.",
            "owner_eta": "N/A",
        },
    }

    info = defect_knowledge.get(canonical_class)
    if info is None:
        return {
            "defect_class": canonical_class,
            "model_confidence": round(confidence, 3),
            "confidence_interpretation": (
                f"The model confidence is {confidence_level}; no matching rule found."
            ),
            "summary": "The detected pattern does not match known defect categories.",
            "pattern_analysis": "Pattern unrecognised — manual review required.",
            "probable_root_cause": "Unknown.",
            "recommended_action": "Manual inspection and expert review are advised.",
            "severity_assessment": "Unknown",
            "risk_level": "Unknown",
            "immediate_containment": "Hold wafer pending expert review.",
            "validation_steps": "Expert review required.",
            "owner_eta": "QA Engineer — ASAP.",
            "genai_note": "Fallback rules were used. Connect a GenAI provider for dynamic reasoning.",
        }

    return {
        "defect_class": canonical_class,
        "model_confidence": round(confidence, 3),
        "confidence_interpretation": (
            f"The model confidence is {confidence_level}; treat this hypothesis accordingly."
        ),
        "summary": info["cause"],
        "pattern_analysis": info["pattern_reasoning"],
        "probable_root_cause": info["cause"],
        "recommended_action": info["action"],
        "severity_assessment": info["severity"],
        "risk_level": info["severity"],
        "immediate_containment": info["containment"],
        "validation_steps": info["validation"],
        "owner_eta": info["owner_eta"],
        "genai_note": "Fallback rules were used. Connect a GenAI provider for dynamic reasoning.",
    }


# ---------------------------------------------------------------------------
# Gemini GenAI response
# ---------------------------------------------------------------------------

def _gemini_response(
    canonical_class: str,
    confidence: float,
    context_hint: str,
) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        import google.generativeai as genai  # type: ignore
    except Exception:
        return None

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    llm = genai.GenerativeModel(model_name)

    confidence_level = _confidence_level(confidence)
    prompt = f"""
You are a semiconductor process engineer assistant. Produce a concise, actionable root-cause analysis.

Return ONLY valid JSON with exactly these keys:
  summary, confidence_interpretation, pattern_analysis, probable_root_cause,
  recommended_action, severity_assessment, risk_level,
  immediate_containment, validation_steps, owner_eta

Inputs:
- defect_class: {canonical_class}
- model_confidence: {confidence:.3f}
- confidence_level: {confidence_level}
- context_hint: {context_hint}

Guidelines:
- Keep each field under 2 sentences.
- Avoid generic phrases; be specific and practical.
- severity_assessment and risk_level: one of None, Low, Medium, High, Critical.
- immediate_containment: what to do RIGHT NOW to stop yield loss.
- validation_steps: how to confirm the fix worked.
- owner_eta: role responsible + expected response time.
"""

    try:
        response = llm.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 600,
                "response_mime_type": "application/json",
            },
        )
        text = response.text or ""
        data = json.loads(text)
        if not isinstance(data, dict):
            return None

        required = [
            "summary",
            "confidence_interpretation",
            "pattern_analysis",
            "probable_root_cause",
            "recommended_action",
            "severity_assessment",
            "risk_level",
            "immediate_containment",
            "validation_steps",
            "owner_eta",
        ]
        if not all(key in data for key in required):
            return None

        data["defect_class"] = canonical_class
        data["model_confidence"] = round(confidence, 3)
        data["genai_note"] = "Generated by Gemini."
        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def analyze_defect(defect_class: str, confidence: float) -> Dict[str, Any]:
    """
    Produce a structured root-cause payload for *defect_class* + *confidence*.

    Uses Gemini if GEMINI_API_KEY is set; falls back to rule-based analysis.
    The *defect_class* string is normalised before lookup so that raw model
    labels like 'Edge ring' correctly resolve to 'edge_ring' rules.
    """
    # Normalise raw model label → canonical snake_case
    canonical = normalize_class(defect_class)

    hint_map = {
        "center": "Defects cluster near wafer center.",
        "donut": "Defects form a donut-shaped ring at mid-radius.",
        "edge_loc": "Defects appear at a localized edge position.",
        "edge_ring": "Defects form a ring near the wafer edge.",
        "local": "Defects appear in a localized cluster.",
        "near_full": "Defects cover most of the wafer surface.",
        "none": "No defects detected.",
        "random": "Defects are scattered across the wafer.",
        "scratch": "Defects appear as linear scratches.",
        "clean": "No significant defects detected.",
    }
    context_hint = hint_map.get(canonical, f"Pattern type: {canonical}.")

    gemini_payload = _gemini_response(canonical, confidence, context_hint)
    payload = gemini_payload if gemini_payload is not None else _fallback_rules(canonical, confidence)

    # Ensure cause_summary is always present (used by history persistence)
    summary = payload.get("summary") or payload.get("probable_root_cause") or ""
    payload["cause_summary"] = summary[:160] if summary else "Cause analysis unavailable."

    return payload
