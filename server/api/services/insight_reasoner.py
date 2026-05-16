"""
RAG Pipeline - Step 5: Retrieval-Augmented Insight Generation
==============================================================
Chains the Step-4 retriever with a grounded Gemini prompt to produce
a structured AI insight for the AutoYield AI Insight Engine UI card.

Public API
----------
    from api.services.insight_reasoner import generate_ai_insight

    result = generate_ai_insight(observation)
    # result → dict with keys: summary, reasoning_basis, certainty,
    #                          recommended_checks, rag_sources, fallback_used

Environment variables
---------------------
    GEMINI_API_KEY   — required for LLM calls (reads from .env via os.getenv)
    GEMINI_MODEL     — optional, defaults to "gemini-1.5-flash"

Fallback behaviour
------------------
    If Gemini is unavailable or returns bad JSON, a deterministic
    fallback response is returned.  The API never crashes.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("autoyield.insight_reasoner")
if not LOGGER.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(_h)
LOGGER.setLevel(logging.INFO)

# ── Lazy-import the Step-4 retriever (avoids circular imports) ────────────────
def _get_retrieve():
    try:
        from search_faiss_index import retrieve  # project root module
        return retrieve
    except ImportError:
        LOGGER.warning("search_faiss_index not found — RAG retrieval disabled.")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: confidence bucket
# ─────────────────────────────────────────────────────────────────────────────
def _confidence_level(confidence: float) -> str:
    if confidence >= 0.70:
        return "high"
    if confidence >= 0.45:
        return "moderate"
    return "low"


# ─────────────────────────────────────────────────────────────────────────────
# Function 1: build_retrieval_query
# ─────────────────────────────────────────────────────────────────────────────
def build_retrieval_query(observation: Dict[str, Any]) -> str:
    """
    Build a descriptive semantic query from the structured observation dict.
    Combines prediction label, confidence category, heatmap behaviour,
    drift trend, and process stage into one natural-language query string
    that is well-suited for sentence-transformer retrieval.
    """
    parts: List[str] = []

    label      = observation.get("prediction_label", "")
    confidence = float(observation.get("confidence", 0.5))
    conf_level = _confidence_level(confidence)

    if label:
        parts.append(f"{label} wafer defect pattern")

    if conf_level == "low":
        parts.append("low confidence uncertain classification")
    elif conf_level == "moderate":
        parts.append("moderate confidence borderline prediction")

    heatmap = observation.get("heatmap_analysis", {})
    region  = heatmap.get("dominant_region", "")
    spread  = float(heatmap.get("spread_score", 0))
    hotspot = int(heatmap.get("num_hotspots", 0))

    if region:
        parts.append(f"{region} activation region")
    if spread > 0.6:
        parts.append("diffuse spread broad pattern contamination")
    if hotspot > 4:
        parts.append("multiple hotspots distributed anomaly")

    drift = observation.get("drift", {})
    trend = drift.get("trend", "")
    if trend == "rising":
        parts.append("rising model drift process variation uncertainty")
    elif trend == "falling":
        parts.append("improving drift model recovery")

    meta  = observation.get("metadata", {})
    stage = meta.get("process_stage", "")
    if stage:
        parts.append(f"{stage} process stage defect")

    return " ".join(parts) if parts else "wafer defect analysis"


# ─────────────────────────────────────────────────────────────────────────────
# Function 2: build_prompt
# ─────────────────────────────────────────────────────────────────────────────
def build_prompt(
    observation: Dict[str, Any],
    retrieved_chunks: List[Dict[str, Any]],
) -> str:
    """
    Assemble the grounded LLM prompt with strict JSON requirements.
    """
    label      = observation.get("prediction_label", "unknown")
    confidence = float(observation.get("confidence", 0.0))
    conf_level = _confidence_level(confidence)

    heatmap = observation.get("heatmap_analysis", {})
    drift   = observation.get("drift", {})
    meta    = observation.get("metadata", {})

    context_block = ""
    if retrieved_chunks:
        ctx_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            src      = chunk.get("source_file", "unknown")
            text     = chunk.get("text", "").strip()[:600]
            ctx_parts.append(f"[Source {i} — {src}]\n{text}")
        context_block = "\n\n".join(ctx_parts)
    else:
        context_block = "No relevant knowledge retrieved. Base response on observation only."

    prompt = f"""You are a semiconductor wafer inspection reasoning assistant.
Produce a brief, grounded, engineering-level AI insight for the current wafer inspection result.

STRICT INSTRUCTIONS:
- Return ONLY valid JSON and absolutely NOTHING else.
- DO NOT wrap the output in markdown code fences like ```json.
- Keep "summary" short (1-2 sentences).
- Keep lists concise with 1-3 items.
- Ensure "certainty" is exactly one of: "low", "moderate", "high".

REQUIRED SCHEMA:
{{
  "summary": "string",
  "reasoning_basis": ["string", "string"],
  "certainty": "low|moderate|high",
  "recommended_checks": ["string", "string"]
}}

OBSERVED EVIDENCE
-----------------
Predicted class : {label}
Confidence      : {confidence:.3f} ({conf_level})
Heatmap region  : {heatmap.get('dominant_region', 'N/A')}
Spread score    : {heatmap.get('spread_score', 'N/A')}
Hotspots        : {heatmap.get('num_hotspots', 'N/A')}
Max activation  : {heatmap.get('max_activation', 'N/A')}
Drift trend     : {drift.get('trend', 'N/A')}
Flagged tool    : {drift.get('tool', 'N/A')}

RETRIEVED CONTEXT
-----------------
{context_block}

Do NOT invent information. If confidence is low, reflect this cautiousness in your output.
OUTPUT ONLY JSON.
"""
    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# Function 3: call_llm
# ─────────────────────────────────────────────────────────────────────────────
def call_llm(prompt: str) -> Optional[str]:
    """
    Send the prompt to Gemini and return the raw response text robustly.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        LOGGER.info("GEMINI_API_KEY not set — skipping LLM call.")
        return None

    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        LOGGER.warning("google-generativeai not installed. Run: pip install google-generativeai")
        return None

    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        llm = genai.GenerativeModel(model_name)

        response = llm.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
            },
        )
        
        # Robustly extract the text
        if response.candidates:
            cand = response.candidates[0]
            parts = cand.content.parts
            if parts:
                return parts[0].text
            
        # Fallback to standard property if candidate parsing fails
        return response.text if hasattr(response, "text") else None

    except Exception as exc:
        LOGGER.error("Gemini call failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Function 4: parse_llm_json
# ─────────────────────────────────────────────────────────────────────────────
def parse_llm_json(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to parse the LLM response as a structured insight dict.
    Handles markdown fences and extra whitespace.
    """
    if not response_text:
        return None
        
    def _validate_and_repair(data: Any) -> Optional[Dict]:
        if not isinstance(data, dict):
            return None
            
        repaired = {
            "summary": str(data.get("summary", "Analysis completed with no summary provided.")),
            "reasoning_basis": data.get("reasoning_basis", []),
            "certainty": str(data.get("certainty", "low")).lower(),
            "recommended_checks": data.get("recommended_checks", [])
        }
        
        # Coerce arrays
        if isinstance(repaired["reasoning_basis"], str):
            repaired["reasoning_basis"] = [repaired["reasoning_basis"]]
        elif not isinstance(repaired["reasoning_basis"], list):
            repaired["reasoning_basis"] = []
            
        if isinstance(repaired["recommended_checks"], str):
            repaired["recommended_checks"] = [repaired["recommended_checks"]]
        elif not isinstance(repaired["recommended_checks"], list):
            repaired["recommended_checks"] = []
            
        # Ensure certainty is valid
        if repaired["certainty"] not in ["low", "moderate", "high"]:
            repaired["certainty"] = "low"
            
        return repaired

    cleaned = response_text.strip()
    
    # 1. Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    # 2. Try direct parse
    try:
        return _validate_and_repair(json.loads(cleaned))
    except (json.JSONDecodeError, TypeError):
        pass

    # 3. Aggressive extraction (from first { to last })
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = cleaned[start_idx:end_idx+1]
        try:
            return _validate_and_repair(json.loads(json_str))
        except (json.JSONDecodeError, TypeError):
            pass

    LOGGER.warning("Could not parse LLM response as valid JSON. Response length: %d", len(response_text))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Function 5: build_fallback_response
# ─────────────────────────────────────────────────────────────────────────────
def build_fallback_response(
    observation: Dict[str, Any],
    retrieved_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Deterministic fallback when Gemini is unavailable or returns bad JSON.
    Grounded entirely in the observation fields — no hallucination risk.
    """
    label      = observation.get("prediction_label", "unknown")
    confidence = float(observation.get("confidence", 0.0))
    conf_level = _confidence_level(confidence)

    heatmap = observation.get("heatmap_analysis", {})
    region  = heatmap.get("dominant_region", "unspecified")
    spread  = float(heatmap.get("spread_score", 0))

    drift = observation.get("drift", {})
    trend = drift.get("trend", "unknown")
    tool  = drift.get("tool", "unspecified tool")

    meta  = observation.get("metadata", {})
    stage = meta.get("process_stage", "unspecified stage")

    # Derive certainty directly from confidence
    certainty = conf_level  # low / moderate / high

    summary = (
        f"Model predicted '{label}' with {conf_level} confidence ({confidence:.2f}). "
        f"Heatmap shows a {region} activation pattern (spread {spread:.2f}). "
        f"Drift trend is {trend} on {tool}."
    )
    if conf_level == "low":
        summary += " Result is uncertain; manual review is strongly advised."

    reasoning_basis = [
        f"Predicted class '{label}' with {confidence:.3f} confidence ({conf_level}).",
        f"Heatmap dominant region: {region}; spread score: {spread:.2f}.",
        f"Model drift trend: {trend} (tool: {tool}, stage: {stage}).",
    ]
    if retrieved_chunks:
        src = retrieved_chunks[0].get("source_file", "retrieved document")
        reasoning_basis.append(f"RAG context retrieved from {src}.")

    recommended_checks = [
        "Perform manual visual inspection of the flagged wafer.",
        f"Review process logs for {tool} at the {stage} stage.",
        "Compare adjacent wafers in the same lot for consistency.",
    ]
    if conf_level == "low":
        recommended_checks.append("Do not make yield decisions until confidence improves.")

    return {
        "summary":             summary,
        "reasoning_basis":     reasoning_basis,
        "certainty":           certainty,
        "recommended_checks":  recommended_checks,
        "rag_sources":         [c.get("source_file") for c in retrieved_chunks],
        "fallback_used":       True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────
def generate_ai_insight(
    observation: Dict[str, Any],
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Main function — call this from FastAPI or any other consumer.

    Steps:
      1. Build a semantic retrieval query from `observation`.
      2. Retrieve top-k chunks from the FAISS index.
      3. Build a grounded Gemini prompt.
      4. Call Gemini; parse the JSON response.
      5. On any failure, return a deterministic fallback response.

    Returns a dict with keys:
        summary, reasoning_basis, certainty, recommended_checks,
        rag_sources, fallback_used
    """
    LOGGER.info("generate_ai_insight called for label=%s conf=%.3f",
                observation.get("prediction_label"), observation.get("confidence", 0))

    # ── Step 1: retrieval ────────────────────────────────────────────────────
    retrieve = _get_retrieve()
    retrieved_chunks: List[Dict] = []
    query = ""
    if retrieve is not None:
        try:
            query = build_retrieval_query(observation)
            LOGGER.info("RAG query: %s", query)
            retrieved_chunks = retrieve(query, top_k=top_k)
            LOGGER.info("Retrieved %d chunks.", len(retrieved_chunks))
        except Exception as exc:
            LOGGER.warning("Retrieval failed: %s — continuing without RAG context.", exc)

    rag_sources = list({c.get("source_file", "") for c in retrieved_chunks if c.get("source_file")})

    # ── Step 2: build prompt ─────────────────────────────────────────────────
    prompt = build_prompt(observation, retrieved_chunks)

    # ── Step 3: call LLM ────────────────────────────────────────────────────
    raw_response = call_llm(prompt)
    if raw_response:
        LOGGER.info(f"Raw Gemini Response Length: {len(raw_response)}")
        with open("gemini_debug.txt", "w", encoding="utf-8") as f:
            f.write(repr(raw_response))
    else:
        LOGGER.info("Raw Gemini Response is empty/None")
    
    # ── Step 4: parse response ───────────────────────────────────────────────
    parsed = None
    if raw_response:
        parsed = parse_llm_json(raw_response)
        if parsed:
            LOGGER.info("Successfully parsed Gemini JSON response.")

    # ── Step 5: return or fallback ───────────────────────────────────────────
    if parsed is not None:
        parsed["rag_sources"]   = rag_sources
        parsed["fallback_used"] = False
        
        # Add debug info for verification if requested
        parsed["_debug"] = {
            "query": query,
            "raw_response": raw_response
        }
        return parsed

    LOGGER.info("Using deterministic fallback response. Parsing/generation failed.")
    fallback = build_fallback_response(observation, retrieved_chunks)
    fallback["rag_sources"] = rag_sources
    return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Local test runner — run this file directly to test without FastAPI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

    SAMPLE_OBSERVATION = {
        "prediction_label": "random",
        "confidence": 0.38,
        "heatmap_analysis": {
            "dominant_region": "diffuse",
            "spread_score": 0.74,
            "num_hotspots": 6,
            "max_activation": 0.91,
        },
        "drift": {
            "current_score": 0.67,
            "trend": "rising",
            "tool": "Litho-04",
        },
        "metadata": {
            "lot_id": "L-9921",
            "process_stage": "lithography",
        },
    }

    print("\n" + "=" * 64)
    print("  AutoYield AI — Insight Reasoner local test")
    print("=" * 64)
    print("  Input observation:")
    print(json.dumps(SAMPLE_OBSERVATION, indent=4))
    print()

    result = generate_ai_insight(SAMPLE_OBSERVATION, top_k=5)

    print("  Insight result:")
    print(json.dumps(result, indent=4))
    print("=" * 64 + "\n")
