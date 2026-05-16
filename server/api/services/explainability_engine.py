from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from src.utils.ontology import normalize_class

LOGGER = logging.getLogger("autoyield.explainability_engine")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)


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


def _listify(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _text(value: Any, fallback: str = "Not available") -> str:
    if value is None:
        return fallback
    normalized = str(value).strip()
    return normalized or fallback


def _title_case_label(value: Any) -> str:
    return _text(value, "Unknown").replace("_", " ").replace("-", " ").title()


def _confidence_level(confidence: float) -> str:
    if confidence >= 0.70:
        return "high"
    if confidence >= 0.45:
        return "moderate"
    return "low"


def _severity_text(value: Any) -> str:
    text = _text(value, "Unknown")
    return text if text != "Not available" else "Unknown"


def _get_retrieve():
    try:
        from search_faiss_index import retrieve  # type: ignore

        return retrieve
    except BaseException:
        pass

    try:
        from scripts.rag.search_faiss_index import retrieve  # type: ignore

        return retrieve
    except BaseException as exc:
        LOGGER.warning("RAG retriever unavailable: %s", exc)
        return None


def build_retrieval_query(observation: Dict[str, Any]) -> str:
    label = normalize_class(_text(observation.get("prediction_label"), "unknown"))
    confidence = _safe_float(observation.get("confidence"), 0.0)
    confidence_level = _confidence_level(confidence)
    heatmap = observation.get("heatmap_analysis") or {}
    drift = observation.get("drift") or {}
    metadata = observation.get("metadata") or {}

    parts = [
        f"{label} wafer defect morphology",
        f"{confidence_level} confidence semiconductor inspection",
        _text(heatmap.get("dominant_region"), ""),
        f"spread {_safe_float(heatmap.get('spread_score'), 0.0):.2f}",
        f"hotspots {_safe_int(heatmap.get('num_hotspots'), 0)}",
        _severity_text(observation.get("severity")),
        _text(drift.get("trend"), ""),
        _text(metadata.get("inspection_tool"), ""),
        _text(metadata.get("process_stage"), ""),
    ]

    if _safe_float(heatmap.get("spread_score"), 0.0) > 0.55:
        parts.append("diffuse activation contamination process variation")
    else:
        parts.append("localized activation defect region")

    if observation.get("drift", {}).get("drift_detected"):
        parts.append("model drift process shift yield engineering")

    return " ".join(part for part in parts if part)


def _format_context_block(retrieved_chunks: List[Dict[str, Any]]) -> str:
    if not retrieved_chunks:
        return "No relevant knowledge retrieved. Use only the inspection signals."

    context_parts = []
    for index, chunk in enumerate(retrieved_chunks, start=1):
        source = chunk.get("source_file", "unknown")
        text = _text(chunk.get("text"), "")[:700]
        context_parts.append(f"[Source {index} - {source}]\n{text}")
    return "\n\n".join(context_parts)


def build_prompt(observation: Dict[str, Any], retrieved_chunks: List[Dict[str, Any]]) -> str:
    heatmap = observation.get("heatmap_analysis") or {}
    drift = observation.get("drift") or {}
    metadata = observation.get("metadata") or {}
    top_predictions = observation.get("top_predictions") or []
    recent_history = observation.get("recent_history") or []

    return f"""You are an AI yield engineering assistant analyzing semiconductor wafer defects.

Use the provided inspection signals, explainability metrics, and retrieved knowledge base context to explain the model's prediction.

Your explanation must include:
- Why the model predicted this defect class
- What regions of the wafer influenced the prediction
- What heatmap patterns were observed
- Possible process-related root causes
- Confidence interpretation
- Engineering implications
- Recommended diagnostic steps

Avoid generic statements.
Explain the reasoning using semiconductor process knowledge.

STRICT OUTPUT RULES:
- Return ONLY valid JSON.
- Do not include markdown fences.
- Keep the total length between 200 and 350 words.
- Every section must include bullet summaries and 3 to 6 explanatory sentences.
- The answer must feel like engineering analysis, not a chatbot reply.

REQUIRED JSON SCHEMA:
{{
  "summary": "string",
  "certainty": "low|moderate|high",
  "prediction_reasoning": {{
    "bullets": ["string"],
    "explanation": ["string"]
  }},
  "heatmap_interpretation": {{
    "bullets": ["string"],
    "explanation": ["string"]
  }},
  "defect_pattern_context": {{
    "bullets": ["string"],
    "explanation": ["string"]
  }},
  "confidence_analysis": {{
    "bullets": ["string"],
    "explanation": ["string"]
  }},
  "drift_impact": {{
    "bullets": ["string"],
    "explanation": ["string"]
  }},
  "engineering_interpretation": {{
    "bullets": ["string"],
    "explanation": ["string"]
  }},
  "recommended_investigation_steps": ["string"]
}}

INSPECTION SIGNALS
- Predicted defect class: {_title_case_label(observation.get("prediction_label"))}
- Confidence score: {_safe_float(observation.get("confidence"), 0.0):.3f}
- Severity level: {_severity_text(observation.get("severity"))}
- Dominant wafer region: {_text(heatmap.get("dominant_region"))}
- Hotspot count: {_safe_int(heatmap.get("num_hotspots"), 0)}
- Activation spread: {_safe_float(heatmap.get("spread_score"), 0.0):.3f}
- Maximum activation: {_safe_float(heatmap.get("max_activation"), 0.0):.3f}
- Drift detected: {"yes" if drift.get("drift_detected") else "no"}
- Drift events in window: {_safe_int(drift.get("recent_drift_events"), 0)}
- Drift threshold: {_safe_float(drift.get("threshold"), 0.45):.2f}
- Inspection tool: {_text(metadata.get("inspection_tool"))}
- Process stage: {_text(metadata.get("process_stage"))}
- Lot ID: {_text(metadata.get("lot_id"))}
- Top predictions: {json.dumps(top_predictions[:5], ensure_ascii=True)}
- Recent inspection history: {json.dumps(recent_history[:5], ensure_ascii=True)}

RETRIEVED CONTEXT
{_format_context_block(retrieved_chunks)}
"""


def call_llm(prompt: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        LOGGER.info("GEMINI_API_KEY not set; explainability engine will use fallback.")
        return None

    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        LOGGER.warning("google-generativeai not installed. Explainability engine will use fallback.")
        return None

    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        max_output_tokens = _safe_int(os.getenv("GEMINI_EXPLAINABILITY_MAX_OUTPUT_TOKENS", "2048"), 2048)
        llm = genai.GenerativeModel(model_name)
        response = llm.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": max_output_tokens,
                "response_mime_type": "application/json",
            },
        )

        if response.candidates:
            candidate = response.candidates[0]
            parts = getattr(candidate.content, "parts", None) or []
            if parts:
                return getattr(parts[0], "text", None)

        return response.text if hasattr(response, "text") else None
    except Exception as exc:
        LOGGER.error("Gemini explainability call failed: %s", exc)
        return None


def _validate_section(section: Any) -> Dict[str, List[str]]:
    if not isinstance(section, dict):
        return {"bullets": [], "explanation": []}

    bullets = [_text(item) for item in _listify(section.get("bullets")) if _text(item, "")]
    explanation = [_text(item) for item in _listify(section.get("explanation")) if _text(item, "")]
    return {
        "bullets": bullets[:6],
        "explanation": explanation[:6],
    }


def parse_llm_json(response_text: str) -> Optional[Dict[str, Any]]:
    if not response_text:
        return None

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    payloads = [cleaned]
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        payloads.append(cleaned[start_idx : end_idx + 1])

    for payload in payloads:
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(parsed, dict):
            continue

        result = {
            "summary": _text(parsed.get("summary"), ""),
            "certainty": _text(parsed.get("certainty"), "low").lower(),
            "prediction_reasoning": _validate_section(parsed.get("prediction_reasoning")),
            "heatmap_interpretation": _validate_section(parsed.get("heatmap_interpretation")),
            "defect_pattern_context": _validate_section(parsed.get("defect_pattern_context")),
            "confidence_analysis": _validate_section(parsed.get("confidence_analysis")),
            "drift_impact": _validate_section(parsed.get("drift_impact")),
            "engineering_interpretation": _validate_section(parsed.get("engineering_interpretation")),
            "recommended_investigation_steps": [
                _text(item) for item in _listify(parsed.get("recommended_investigation_steps")) if _text(item, "")
            ][:8],
        }

        if result["certainty"] not in {"low", "moderate", "high"}:
            result["certainty"] = "low"

        if not result["prediction_reasoning"]["explanation"]:
            continue

        return result

    LOGGER.warning("Could not parse explainability response as JSON. Length=%d", len(response_text))
    return None


def _context_sentences_from_rag(retrieved_chunks: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    sentences: List[str] = []
    for chunk in retrieved_chunks[:limit]:
        text = _text(chunk.get("text"), "")
        if not text:
            continue
        candidate = re.split(r"(?<=[.!?])\s+", text)
        for sentence in candidate:
            normalized = sentence.strip()
            if len(normalized) >= 50:
                sentences.append(normalized)
                break
    return sentences[:limit]


def build_fallback_response(observation: Dict[str, Any], retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    label = normalize_class(_text(observation.get("prediction_label"), "unknown"))
    label_title = _title_case_label(label)
    confidence = _safe_float(observation.get("confidence"), 0.0)
    certainty = _confidence_level(confidence)
    severity = _severity_text(observation.get("severity"))
    heatmap = observation.get("heatmap_analysis") or {}
    drift = observation.get("drift") or {}
    metadata = observation.get("metadata") or {}
    top_predictions = _listify(observation.get("top_predictions"))
    rag_sentences = _context_sentences_from_rag(retrieved_chunks)

    dominant_region = _text(heatmap.get("dominant_region"), "unknown region")
    spread_score = _safe_float(heatmap.get("spread_score"), 0.0)
    hotspot_count = _safe_int(heatmap.get("num_hotspots"), 0)
    max_activation = _safe_float(heatmap.get("max_activation"), 0.0)
    drift_detected = bool(drift.get("drift_detected"))
    drift_events = _safe_int(drift.get("recent_drift_events"), 0)
    tool = _text(metadata.get("inspection_tool"), "inspection tool")
    stage = _text(metadata.get("process_stage"), "wafer inspection")

    if spread_score <= 0.20:
        heatmap_interpretation = [
            "The activation footprint is compact rather than diffuse.",
            "A low spread score indicates the classifier focused on a narrower visual region.",
            "This usually supports a localized anomaly hypothesis instead of broad contamination.",
        ]
    else:
        heatmap_interpretation = [
            "The activation footprint extends across a broader portion of the wafer image.",
            "A higher spread score suggests the model saw distributed evidence rather than a single compact hotspot.",
            "That pattern is more consistent with process variation or contamination than a single mechanical mark.",
        ]

    prediction_reasoning_explanation = [
        f"The model classified the wafer as {label_title} with {confidence * 100:.1f}% confidence.",
        f"Attention was strongest in the {dominant_region}, which influenced the class assignment.",
        f"The severity signal is {severity}, so the prediction should be treated as an engineering screening result rather than a cosmetic label.",
        f"The top-ranked pattern matched known {label.replace('_', ' ')} morphology more closely than the secondary candidates.",
    ]

    defect_context_explanation = rag_sentences or [
        f"{label_title} defects are commonly tied to process-specific morphology that appears repeatable across similar wafer regions.",
        f"In semiconductor inspection workflows, that pattern is typically reviewed alongside tool state and recent lot history.",
        f"The retrieved knowledge was limited, so this interpretation is grounded primarily in the inspection signals and model output.",
    ]

    confidence_explanation = [
        f"A {confidence * 100:.1f}% score corresponds to {certainty} classifier certainty for this inspection.",
        "Confidence above 70% generally indicates the image resembles known examples in the trained feature space.",
        "Confidence should still be interpreted together with drift state, competing classes, and process context before yield decisions are made.",
    ]

    if len(top_predictions) >= 2:
        top_1 = _safe_float(top_predictions[0].get("prob"), 0.0)
        top_2 = _safe_float(top_predictions[1].get("prob"), 0.0)
        confidence_explanation.append(
            f"The gap between the top two classes is {(top_1 - top_2) * 100:.1f} percentage points, which helps indicate class separation."
        )

    drift_explanation = [
        f"Drift monitoring is {'active' if drift_detected else 'inactive'} for this inspection.",
        f"The rolling window contains {drift_events} recent drift event(s), which affects how strongly this prediction should be trusted in isolation.",
        f"When drift appears, possible causes include tool calibration changes, illumination shifts, or upstream process changes on {tool}.",
        "Predictions from drift-flagged windows should be validated against adjacent wafers and process logs.",
    ]

    engineering_explanation = [
        f"The combined class signal, heatmap focus, and severity point to a likely issue during the {stage} stage.",
        f"Potential engineering contributors include regional non-uniformity, tool instability, or contamination associated with {tool}.",
        "The explainability output should be used to guide investigation priority, not to replace microscopy review or tool diagnostics.",
    ]

    recommended_steps = [
        "Inspect the Grad-CAM heatmap and raw wafer image together.",
        "Validate that the highlighted region aligns with the suspected defect morphology.",
        f"Review {tool} process logs around the inspection timestamp.",
        "Compare neighboring wafers from the same lot for recurrence.",
        "Check recent calibration, illumination, and recipe adjustments.",
        "Escalate to process engineering if repeated drift or the same morphology recurs.",
    ]

    summary = (
        f"The inspection was classified as {label_title} with {confidence * 100:.1f}% confidence. "
        f"Attention concentrated in the {dominant_region} with spread {spread_score:.3f} and {hotspot_count} hotspot(s)."
    )

    return {
        "summary": summary,
        "certainty": certainty,
        "prediction_reasoning": {
            "bullets": [
                f"Predicted defect class: {label_title}",
                f"Confidence score: {confidence * 100:.1f}%",
                f"Severity level: {severity}",
                f"Dominant wafer region: {dominant_region}",
            ],
            "explanation": prediction_reasoning_explanation,
        },
        "heatmap_interpretation": {
            "bullets": [
                f"Dominant activation region: {dominant_region}",
                f"Hotspot count: {hotspot_count}",
                f"Spread score: {spread_score:.3f}",
                f"Maximum activation intensity: {max_activation:.3f}",
            ],
            "explanation": heatmap_interpretation,
        },
        "defect_pattern_context": {
            "bullets": [
                f"Retrieved context documents: {len(retrieved_chunks)}",
                f"Process stage: {stage}",
                f"Inspection tool: {tool}",
            ],
            "explanation": defect_context_explanation,
        },
        "confidence_analysis": {
            "bullets": [
                f"Model confidence: {confidence * 100:.1f}%",
                f"Confidence bucket: {certainty}",
                f"Secondary candidates considered: {max(len(top_predictions) - 1, 0)}",
            ],
            "explanation": confidence_explanation,
        },
        "drift_impact": {
            "bullets": [
                f"Drift detection: {'Active' if drift_detected else 'Clear'}",
                f"Recent drift events: {drift_events}",
                f"Inspection tool: {tool}",
                f"Process stage: {stage}",
            ],
            "explanation": drift_explanation,
        },
        "engineering_interpretation": {
            "bullets": [
                f"Likely affected stage: {stage}",
                f"Tool under review: {tool}",
                f"Severity: {severity}",
            ],
            "explanation": engineering_explanation,
        },
        "recommended_investigation_steps": recommended_steps,
    }


def _flatten_reasoning_basis(explanation: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    section_keys = [
        "prediction_reasoning",
        "heatmap_interpretation",
        "defect_pattern_context",
        "confidence_analysis",
        "drift_impact",
        "engineering_interpretation",
    ]
    for section_key in section_keys:
        section = explanation.get(section_key) or {}
        items.extend(_listify(section.get("bullets"))[:2])
    return [_text(item) for item in items if _text(item, "")][:10]


def generate_explanation(observation: Dict[str, Any], top_k: int = 5) -> Dict[str, Any]:
    LOGGER.info(
        "generate_explanation called for label=%s conf=%.3f",
        observation.get("prediction_label"),
        _safe_float(observation.get("confidence"), 0.0),
    )

    retrieve = _get_retrieve()
    retrieved_chunks: List[Dict[str, Any]] = []
    query = ""
    if retrieve is not None:
        try:
            query = build_retrieval_query(observation)
            retrieved_chunks = retrieve(query, top_k=top_k)
            LOGGER.info("Explainability retrieval returned %d chunks.", len(retrieved_chunks))
        except Exception as exc:
            LOGGER.warning("Explainability retrieval failed: %s", exc)

    rag_sources = list({chunk.get("source_file", "") for chunk in retrieved_chunks if chunk.get("source_file")})
    prompt = build_prompt(observation, retrieved_chunks)
    raw_response = call_llm(prompt)
    parsed = parse_llm_json(raw_response) if raw_response else None
    explanation = parsed if parsed is not None else build_fallback_response(observation, retrieved_chunks)

    explanation["rag_sources"] = rag_sources
    explanation["fallback_used"] = parsed is None
    explanation["metadata"] = {
        "inspection_tool": _text((observation.get("metadata") or {}).get("inspection_tool")),
        "process_stage": _text((observation.get("metadata") or {}).get("process_stage")),
        "lot_id": _text((observation.get("metadata") or {}).get("lot_id")),
        "target_layer": _text((observation.get("metadata") or {}).get("target_layer")),
    }
    explanation["reasoning_basis"] = _flatten_reasoning_basis(explanation)
    explanation["recommended_checks"] = _listify(explanation.get("recommended_investigation_steps"))[:6]
    explanation["word_count"] = len(" ".join(
        _listify(explanation.get("summary"))
        + _flatten_reasoning_basis(explanation)
        + _listify(explanation.get("recommended_investigation_steps"))
    ).split())
    explanation["_debug"] = {"query": query} if query else {}
    return explanation
