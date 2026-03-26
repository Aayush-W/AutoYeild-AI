"""
Rule-first root-cause analysis agent for wafer defect classification.

Design:
- Validated fallback rules remain the primary source of truth.
- Gemini is optional and only restructures or lightly expands rule outputs.
- RAG context is supporting context only and must not override rule outputs.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from src.utils.ontology import normalize_class


def _confidence_level(confidence: float) -> str:
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.4:
        return "moderate"
    return "low"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    normalized = str(value).strip()
    return normalized or fallback


def _listify(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _title_case_label(value: Any) -> str:
    label = _text(value, "unknown")
    return label.replace("_", " ").replace("-", " ").title()


def _split_actions(action_text: str) -> List[str]:
    normalized = _text(action_text)
    if not normalized:
        return []
    parts = re.split(r",\s*| and ", normalized)
    cleaned = []
    for part in parts:
        item = part.strip(" .")
        if item:
            cleaned.append(item[0].upper() + item[1:] if len(item) > 1 else item.upper())
    return cleaned


def _group_checklist_items(rule_payload: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    recommended_action = _split_actions(rule_payload.get("recommended_action", ""))
    containment = _split_actions(rule_payload.get("immediate_containment", ""))
    validation = _split_actions(rule_payload.get("validation_steps", ""))
    tool = _text(context.get("inspection_tool"), "the inspection tool")
    process_stage = _text(context.get("process_stage"), "the process step")

    sections = [
        {
            "title": "Process Investigation",
            "items": [
                "Review wafer heatmap and original inspection image",
                f"Validate highlighted defect morphology against the predicted pattern during {process_stage}",
            ],
        },
        {
            "title": "Tool Diagnostics",
            "items": recommended_action[:2] or [f"Inspect {tool} for the rule-triggered process issue"],
        },
        {
            "title": "Process Log Review",
            "items": [
                f"Review recent {tool} logs and calibration history",
                "Compare defect frequency across neighboring wafers in the same lot",
            ],
        },
        {
            "title": "Escalation",
            "items": (containment[:1] + validation[:1]) or ["Escalate to the responsible engineering owner if the pattern repeats"],
        },
    ]

    total_items = 0
    trimmed_sections: List[Dict[str, Any]] = []
    for section in sections:
        items = []
        for item in section["items"]:
            if not item:
                continue
            if total_items >= 8:
                break
            items.append(item.rstrip("."))
            total_items += 1
        if items:
            trimmed_sections.append({"title": section["title"], "items": items})
        if total_items >= 8:
            break
    return trimmed_sections


def _fallback_rules(canonical_class: str, confidence: float) -> Dict[str, Any]:
    confidence_level = _confidence_level(confidence)

    defect_knowledge: Dict[str, Dict[str, str]] = {
        "center": {
            "pattern_reasoning": (
                "The defect pattern is concentrated near the wafer center, which typically correlates "
                "with non-uniform thermal or pressure conditions during central process phases."
            ),
            "cause": "Instability in center-zone temperature or chamber pressure during deposition or etching steps.",
            "action": "Review thermal uniformity maps, recalibrate center-zone pressure control, and inspect recent process drift logs.",
            "severity": "Medium",
            "containment": "Quarantine affected lot and run a thermal profile diagnostic.",
            "validation": "Confirm center-zone uniformity with a controlled test wafer run.",
            "owner_eta": "Process Engineer - within 4 hours.",
            "rule_triggered": "center_zone_thermal_instability",
        },
        "edge_ring": {
            "pattern_reasoning": (
                "Defects forming a ring near the wafer edge often indicate mechanical or alignment-related issues, "
                "especially during polishing or edge exclusion steps."
            ),
            "cause": "Wafer misalignment, edge over-polishing, or uneven edge pressure application.",
            "action": "Verify wafer centering calibration, inspect edge exclusion parameters, and check polishing pad wear.",
            "severity": "High",
            "containment": "Stop the CMP tool run and escalate to the equipment team.",
            "validation": "Re-run edge scan on the next lot to confirm resolution.",
            "owner_eta": "Equipment Engineer - within 2 hours.",
            "rule_triggered": "edge_ring_mechanical_alignment",
        },
        "edge_loc": {
            "pattern_reasoning": (
                "Localized edge defects suggest a fixed-position contamination source or a tool-specific "
                "edge-exclusion misconfiguration."
            ),
            "cause": "Fixed contamination source at the wafer edge or asymmetric edge exclusion ring behavior.",
            "action": "Inspect and clean the edge exclusion ring and check notch alignment.",
            "severity": "Medium",
            "containment": "Hold the lot pending edge exclusion parameter review.",
            "validation": "Run a particle scan after cleaning to confirm elimination.",
            "owner_eta": "Process Engineer - within 4 hours.",
            "rule_triggered": "edge_localized_contamination",
        },
        "local": {
            "pattern_reasoning": (
                "Localized defect clusters suggest isolated contamination or transient process disturbances "
                "affecting a small wafer region."
            ),
            "cause": "Localized particle contamination or short-lived chamber instability.",
            "action": "Inspect recent chamber cleaning cycles and analyze tool logs for localized anomalies.",
            "severity": "Medium",
            "containment": "Mark affected dice and continue the lot under enhanced monitoring.",
            "validation": "Verify particle counts after chamber cleaning.",
            "owner_eta": "Tool Owner - within 6 hours.",
            "rule_triggered": "local_cluster_contamination",
        },
        "scratch": {
            "pattern_reasoning": (
                "Linear or directional defect patterns are characteristic of mechanical contact during wafer "
                "handling or transport."
            ),
            "cause": "Physical contact from handling equipment or misaligned wafer transport mechanisms.",
            "action": "Audit wafer handling robots, cassette alignment, and transport paths.",
            "severity": "High",
            "containment": "Isolate the handler and scrap wafers if the scratch crosses active area.",
            "validation": "Inspect the next five wafers from the same handler slot.",
            "owner_eta": "FA Engineer - within 1 hour.",
            "rule_triggered": "scratch_mechanical_contact",
        },
        "random": {
            "pattern_reasoning": (
                "Scattered, non-uniform defects across the wafer are often associated with airborne particles "
                "or sporadic contamination events."
            ),
            "cause": "Random particle deposition from airflow disturbances or filter degradation.",
            "action": "Review cleanroom airflow data and particle counter logs.",
            "severity": "Low",
            "containment": "Continue processing with increased inline monitoring frequency.",
            "validation": "Check the cleanroom particle counter trend for the past 24 hours.",
            "owner_eta": "Facilities Engineer - within 8 hours.",
            "rule_triggered": "random_particle_deposition",
        },
        "donut": {
            "pattern_reasoning": (
                "Donut-shaped defect rings at intermediate radius often indicate spin-coat or bake non-uniformity."
            ),
            "cause": "Resist spin-coat speed deviation or hotplate temperature non-uniformity.",
            "action": "Recalibrate the spin-coater and verify the hotplate temperature profile.",
            "severity": "Medium",
            "containment": "Hold the affected photo lot and rework only if it remains within spec.",
            "validation": "Run a coat uniformity test wafer and verify CD variation under 2 percent.",
            "owner_eta": "Photo Engineer - within 4 hours.",
            "rule_triggered": "donut_coat_uniformity",
        },
        "near_full": {
            "pattern_reasoning": (
                "Defects covering most of the wafer surface indicate a systemic process failure such as complete "
                "etch stop, coat failure, or contaminated chemistry."
            ),
            "cause": "Systemic process failure caused by contaminated chemistry, exhausted bath, or equipment crash.",
            "action": "Stop production, replace chemistry, and perform full tool qualification.",
            "severity": "Critical",
            "containment": "Stop the lot, quarantine the full batch, and notify the shift supervisor immediately.",
            "validation": "Complete a full re-qualification run before restarting production.",
            "owner_eta": "Shift Supervisor - immediately.",
            "rule_triggered": "near_full_systemic_process_failure",
        },
        "none": {
            "pattern_reasoning": "No significant defect patterns were detected across the wafer surface.",
            "cause": "Wafer appears within normal process limits.",
            "action": "No corrective action required. Continue routine monitoring.",
            "severity": "None",
            "containment": "No containment action required.",
            "validation": "Continue standard SPC monitoring.",
            "owner_eta": "N/A",
            "rule_triggered": "clean_pass_through",
        },
        "clean": {
            "pattern_reasoning": "No significant defect patterns were detected across the wafer surface.",
            "cause": "Wafer appears within normal process limits.",
            "action": "No corrective action required. Continue routine monitoring.",
            "severity": "None",
            "containment": "No containment action required.",
            "validation": "Continue standard SPC monitoring.",
            "owner_eta": "N/A",
            "rule_triggered": "clean_pass_through",
        },
    }

    info = defect_knowledge.get(canonical_class)
    if info is None:
        return {
            "defect_class": canonical_class,
            "model_confidence": round(confidence, 3),
            "confidence_interpretation": f"The model confidence is {confidence_level}; no validated rule matched this class.",
            "summary": "The detected pattern does not match a validated defect rule.",
            "pattern_analysis": "Pattern unrecognized. Manual review required.",
            "probable_root_cause": "Unknown root cause pending engineer review.",
            "recommended_action": "Perform manual inspection and route the case to an expert reviewer.",
            "severity_assessment": "Unknown",
            "risk_level": "Unknown",
            "immediate_containment": "Hold the wafer pending expert review.",
            "validation_steps": "Review by process engineering is required.",
            "owner_eta": "QA Engineer - ASAP.",
            "detected_pattern": canonical_class,
            "rule_triggered": "no_validated_rule",
            "suggested_root_cause": "Unknown root cause pending review.",
            "rule_recommended_actions": ["Perform manual inspection", "Escalate to process engineering"],
            "genai_note": "Rule-first fallback was used.",
        }

    return {
        "defect_class": canonical_class,
        "model_confidence": round(confidence, 3),
        "confidence_interpretation": f"The model confidence is {confidence_level}; treat this rule match accordingly.",
        "summary": info["cause"],
        "pattern_analysis": info["pattern_reasoning"],
        "probable_root_cause": info["cause"],
        "recommended_action": info["action"],
        "severity_assessment": info["severity"],
        "risk_level": info["severity"],
        "immediate_containment": info["containment"],
        "validation_steps": info["validation"],
        "owner_eta": info["owner_eta"],
        "detected_pattern": canonical_class,
        "rule_triggered": info["rule_triggered"],
        "suggested_root_cause": info["cause"],
        "rule_recommended_actions": _split_actions(info["action"]),
        "genai_note": "Rule-first fallback was used.",
    }


def _get_retrieve():
    try:
        from search_faiss_index import retrieve  # type: ignore

        return retrieve
    except BaseException:
        pass

    try:
        from scripts.rag.search_faiss_index import retrieve  # type: ignore

        return retrieve
    except BaseException:
        return None


def _build_retrieval_query(rule_payload: Dict[str, Any], context: Dict[str, Any]) -> str:
    parts = [
        f"{rule_payload.get('defect_class', 'unknown')} wafer defect root cause",
        _text(context.get("heatmap_region")),
        _text(context.get("process_stage")),
        _text(context.get("inspection_tool")),
        _text(rule_payload.get("rule_triggered")),
        _text(rule_payload.get("suggested_root_cause")),
    ]
    return " ".join(part for part in parts if part)


def _retrieve_context(rule_payload: Dict[str, Any], context: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
    retrieve = _get_retrieve()
    if retrieve is None:
        return []

    try:
        return retrieve(_build_retrieval_query(rule_payload, context), top_k=top_k)
    except BaseException:
        return []


def _build_summary_paragraph(rule_payload: Dict[str, Any], context: Dict[str, Any]) -> str:
    defect_class = _title_case_label(rule_payload.get("defect_class"))
    confidence = _safe_float(rule_payload.get("model_confidence"), 0.0) * 100
    drift_status = "active" if context.get("drift_status") else "clear"
    severity = _text(rule_payload.get("severity_assessment"), "Unknown")
    process_stage = _text(context.get("process_stage"), "the current process stage")
    return (
        f"The inspection detected a {defect_class.lower()} defect pattern with {confidence:.1f}% model confidence. "
        f"The validated rule engine links this pattern to {rule_payload.get('suggested_root_cause')}. "
        f"Drift monitoring is {drift_status}, so the result should be reviewed in the context of recent process behavior at {process_stage}. "
        f"Based on the available rule signals, this case is categorized as {severity.lower()} severity and should be checked against the relevant process controls."
    )


def _build_probable_root_cause_box(
    rule_payload: Dict[str, Any],
    context: Dict[str, Any],
    retrieved_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    defect_class = _title_case_label(rule_payload.get("defect_class"))
    confidence = _safe_float(rule_payload.get("model_confidence"), 0.0) * 100
    heatmap_region = _text(context.get("heatmap_region"), "unknown region")
    activation_spread = _safe_float(context.get("activation_spread"), 0.0)
    hotspot_count = _safe_int(context.get("hotspot_count"), 0)

    evidence = [
        f"The classifier identified a {defect_class.lower()} pattern with {confidence:.1f}% confidence.",
        f"Heatmap activation is concentrated near {heatmap_region}.",
        f"Activation spread is {activation_spread:.3f} with {hotspot_count} hotspot(s).",
        f"The validated rule engine triggered {rule_payload.get('rule_triggered')}, which maps to {rule_payload.get('suggested_root_cause')}.",
    ]
    if retrieved_chunks:
        source = _text(retrieved_chunks[0].get("source_file"), "retrieved process knowledge")
        evidence.append(f"Supporting process context was retrieved from {source}.")

    explanation = (
        f"The most probable cause is {rule_payload.get('suggested_root_cause')}. "
        f"This conclusion is grounded in the validated {rule_payload.get('rule_triggered')} rule rather than free-form generation. "
        f"The defect classification, activation region, and hotspot behavior all align with the expected morphology for this rule path. "
        f"The rule-based pattern analysis indicates {rule_payload.get('pattern_analysis')} "
        f"Taken together, the model output and supporting explainability signals indicate that the issue is likely process-driven rather than random inspection noise."
    )

    return {
        "root_cause_identified": f"{rule_payload.get('suggested_root_cause')}",
        "evidence_signals": evidence,
        "explanation": explanation,
    }


def _build_checklist_box(rule_payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return {"sections": _group_checklist_items(rule_payload, context)}


def _fallback_root_cause_boxes(
    rule_payload: Dict[str, Any],
    context: Dict[str, Any],
    retrieved_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "summary_paragraph": _build_summary_paragraph(rule_payload, context),
        "probable_root_cause": _build_probable_root_cause_box(rule_payload, context, retrieved_chunks),
        "recommended_corrective_action": _build_checklist_box(rule_payload, context),
    }


def _build_llm_prompt(
    rule_payload: Dict[str, Any],
    context: Dict[str, Any],
    retrieved_chunks: List[Dict[str, Any]],
) -> str:
    retrieved_context = "\n\n".join(
        f"[Source {index + 1} - {_text(chunk.get('source_file'), 'unknown')}]\n{_text(chunk.get('text'), '')[:500]}"
        for index, chunk in enumerate(retrieved_chunks[:3])
    ) or "No retrieved context available."

    return f"""
You are organizing root-cause analysis content for the AutoYield AI Root Cause Analysis page.

Important constraints:
- Do not invent new root causes.
- The fallback rule outputs are the primary source of truth.
- Use retrieved context only to support wording that stays consistent with the rule outputs.
- Maintain an engineering tone.
- Avoid generic AI language.

Return ONLY valid JSON with exactly this schema:
{{
  "summary_paragraph": "string",
  "probable_root_cause": {{
    "root_cause_identified": "string",
    "evidence_signals": ["string"],
    "explanation": "string"
  }},
  "recommended_corrective_action": {{
    "sections": [
      {{"title": "string", "items": ["string"]}}
    ]
  }}
}}

Formatting requirements:
- summary_paragraph: one paragraph, 3 to 4 sentences, under 120 words.
- probable_root_cause.explanation: 120 to 180 words.
- recommended_corrective_action: checklist sections only, no paragraphs, 6 to 8 total items.

RULE OUTPUTS - SOURCE OF TRUTH
- detected_pattern: {_text(rule_payload.get("detected_pattern"))}
- rule_triggered: {_text(rule_payload.get("rule_triggered"))}
- suggested_root_cause: {_text(rule_payload.get("suggested_root_cause"))}
- rule_recommended_actions: {json.dumps(_listify(rule_payload.get("rule_recommended_actions")), ensure_ascii=True)}
- severity_level: {_text(rule_payload.get("severity_assessment"))}
- probable_root_cause: {_text(rule_payload.get("probable_root_cause"))}
- pattern_analysis: {_text(rule_payload.get("pattern_analysis"))}
- immediate_containment: {_text(rule_payload.get("immediate_containment"))}
- validation_steps: {_text(rule_payload.get("validation_steps"))}

INSPECTION SIGNALS
- prediction_class: {_text(rule_payload.get("defect_class"))}
- confidence_score: {_safe_float(rule_payload.get("model_confidence"), 0.0):.3f}
- drift_status: {"detected" if context.get("drift_status") else "clear"}
- heatmap_region: {_text(context.get("heatmap_region"))}
- activation_spread: {_safe_float(context.get("activation_spread"), 0.0):.3f}
- hotspot_count: {_safe_int(context.get("hotspot_count"), 0)}
- inspection_tool: {_text(context.get("inspection_tool"))}
- process_stage: {_text(context.get("process_stage"))}

RETRIEVED CONTEXT
{retrieved_context}
"""


def _call_gemini_structuring(prompt: str) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        import google.generativeai as genai  # type: ignore
    except Exception:
        return None

    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        llm = genai.GenerativeModel(model_name)
        response = llm.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 900,
                "response_mime_type": "application/json",
            },
        )
        text = response.text or ""
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def _sanitize_sections(data: Any) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    if not isinstance(data, list):
        return sections
    total_items = 0
    for section in data:
        if not isinstance(section, dict):
            continue
        title = _text(section.get("title"))
        items = []
        for item in _listify(section.get("items")):
            line = _text(item).rstrip(".")
            if not line:
                continue
            if total_items >= 8:
                break
            items.append(line)
            total_items += 1
        if title and items:
            sections.append({"title": title, "items": items})
        if total_items >= 8:
            break
    return sections


def _merge_root_cause_boxes(
    fallback_boxes: Dict[str, Any],
    llm_boxes: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(llm_boxes, dict):
        return fallback_boxes

    probable = llm_boxes.get("probable_root_cause") if isinstance(llm_boxes.get("probable_root_cause"), dict) else {}
    corrective = llm_boxes.get("recommended_corrective_action") if isinstance(llm_boxes.get("recommended_corrective_action"), dict) else {}

    summary_paragraph = _text(llm_boxes.get("summary_paragraph")) or fallback_boxes["summary_paragraph"]
    root_cause_identified = _text(probable.get("root_cause_identified")) or fallback_boxes["probable_root_cause"]["root_cause_identified"]
    evidence_signals = [_text(item) for item in _listify(probable.get("evidence_signals")) if _text(item)]
    explanation = _text(probable.get("explanation")) or fallback_boxes["probable_root_cause"]["explanation"]
    sections = _sanitize_sections(corrective.get("sections"))

    return {
        "summary_paragraph": summary_paragraph,
        "probable_root_cause": {
            "root_cause_identified": root_cause_identified,
            "evidence_signals": evidence_signals or fallback_boxes["probable_root_cause"]["evidence_signals"],
            "explanation": explanation,
        },
        "recommended_corrective_action": {
            "sections": sections or fallback_boxes["recommended_corrective_action"]["sections"],
        },
    }


def analyze_defect(defect_class: str, confidence: float, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Produce a structured root-cause payload for the Root Cause page.

    Validated fallback rules remain authoritative. Gemini only restructures and
    lightly expands those rule outputs.
    """
    canonical = normalize_class(defect_class)
    rule_payload = _fallback_rules(canonical, confidence)
    context = context or {}

    retrieved_chunks = _retrieve_context(rule_payload, context, top_k=3)
    fallback_boxes = _fallback_root_cause_boxes(rule_payload, context, retrieved_chunks)
    llm_boxes = _call_gemini_structuring(_build_llm_prompt(rule_payload, context, retrieved_chunks))
    root_cause_ui = _merge_root_cause_boxes(fallback_boxes, llm_boxes)

    payload = dict(rule_payload)
    payload["summary"] = root_cause_ui["summary_paragraph"]
    payload["cause_summary"] = root_cause_ui["summary_paragraph"][:160]
    payload["root_cause_ui"] = root_cause_ui
    payload["genai_note"] = (
        "Rule-first output structured with Gemini."
        if llm_boxes is not None
        else "Rule-first fallback was used."
    )
    payload["rag_sources"] = [chunk.get("source_file") for chunk in retrieved_chunks if chunk.get("source_file")]
    return payload
