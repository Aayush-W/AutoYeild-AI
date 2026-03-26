# Load .env variables FIRST — before any module reads os.getenv()
from dotenv import load_dotenv
load_dotenv()

import asyncio
import base64
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.inference.run_inference import predict_with_probs
from src.inference.gradcam import generate_gradcam, summarize_gradcam_overlay
from src.reasoning.root_cause_agent import analyze_defect
from src.autonomy.drift_monitor import get_drift_monitor
from src.autonomy.triage_agent import triage
from src.self_improvement.synthetic_generator import generate_synthetic_images

from config.db import async_db
from api.services.explainability_engine import generate_explanation
from api.services.visual_report_generator import generate_visual_report

APP_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = APP_ROOT / "outputs" / "uploads"
SYNTH_DIR = APP_ROOT / "outputs" / "synthetic_images"
GAN_CONFIDENCE_THRESHOLD = 0.50
HUMAN_REVIEW_THRESHOLD = 0.30
RANDOM_CONFIDENCE_THRESHOLD = 0.70
DEFECT_LABEL_OPTIONS = [
    "Center",
    "Donut",
    "Edge Loc",
    "Edge Ring",
    "Local",
    "Near Full",
    "Particle",
    "Random",
    "Scratch",
    "Clean",
    "Other / Unknown",
]


def _get_cors_origins() -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [item.strip() for item in raw.split(",") if item.strip()]

# ---------------------------------------------------------------------------
# Lifespan: warm up drift monitor singleton on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await async_db.command("ping")
    get_drift_monitor()
    yield

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    ext = path.suffix.lower().replace(".", "") or "png"
    return f"data:image/{ext};base64,{data}"

def _compute_summary_metrics(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(history)
    if total == 0:
        return {
            "total_inspections": 0,
            "avg_confidence": 0.0,
            "drift_events": 0,
            "class_distribution": {},
            "last_inspection": None,
        }

    avg_conf = sum(item.get("confidence", 0.0) for item in history) / total
    drift_events = sum(1 for item in history if item.get("drift_detected"))
    class_dist: Dict[str, int] = {}
    for item in history:
        label = item.get("defect_class", "unknown")
        class_dist[label] = class_dist.get(label, 0) + 1

    return {
        "total_inspections": total,
        "avg_confidence": round(avg_conf, 4),
        "drift_events": drift_events,
        "class_distribution": class_dist,
        "last_inspection": history[-1] if history else None,
    }

async def _load_history():
    return await async_db.inspections.find({}, {"_id": 0}).sort("timestamp", 1).to_list(200)

async def _append_history(entry):
    entry["_id"] = entry["inspection_id"]
    await async_db.inspections.insert_one(entry)
    
    # Keep rolling window: drop oldest docs beyond 200
    total_docs = await async_db.inspections.count_documents({})
    if total_docs > 200:
        oldest = await async_db.inspections.find().sort("timestamp", 1).limit(total_docs - 200).to_list(None)
        oldest_ids = [doc["_id"] for doc in oldest]
        if oldest_ids:
            await async_db.inspections.delete_many({"_id": {"$in": oldest_ids}})

async def _load_model_metrics():
    doc = await async_db.model_metrics.find_one({"_id": "singleton"})
    if doc:
        return {k: v for k, v in doc.items() if k != "_id"}
    return {}


async def _route_retraining_sample(
    *,
    inspection_id: str,
    timestamp: str,
    confidence: float,
    model_prediction: str,
    wafer_image: str,
) -> Dict[str, Any]:
    normalized_prediction = str(model_prediction).strip().lower()

    if normalized_prediction == "random":
        review_id = f"RVW-{uuid.uuid4().hex[:12].upper()}"
        doc = {
            "_id": review_id,
            "review_id": review_id,
            "inspection_id": inspection_id,
            "wafer_image": wafer_image,
            "model_prediction": model_prediction,
            "predicted_class": model_prediction,
            "confidence": round(confidence, 4),
            "timestamp": timestamp,
            "review_reason": "Random Class Verification",
            "expert_label": None,
            "verified_label": None,
            "verification_status": False,
            "verified_by_human": False,
            "reviewed": False,
            "status": "pending_review",
            "eligible_for_gan": False,
        }
        await async_db.human_review_queue.replace_one({"_id": review_id}, doc, upsert=True)
        return {
            "confidence_filter_status": "pending_review",
            "allow_for_gan": False,
            "verified_by_human": False,
            "review_queue_id": review_id,
            "uncertain_pool_id": None,
            "review_reason": "Random Class Verification",
        }

    if confidence >= GAN_CONFIDENCE_THRESHOLD:
        return {
            "confidence_filter_status": "eligible_for_gan",
            "allow_for_gan": True,
            "verified_by_human": False,
            "review_queue_id": None,
            "uncertain_pool_id": None,
            "review_reason": None,
        }

    if confidence >= HUMAN_REVIEW_THRESHOLD:
        uncertain_id = f"UNC-{uuid.uuid4().hex[:12].upper()}"
        doc = {
            "_id": uncertain_id,
            "pool_id": uncertain_id,
            "inspection_id": inspection_id,
            "wafer_image": wafer_image,
            "model_prediction": model_prediction,
            "predicted_class": model_prediction,
            "confidence": round(confidence, 4),
            "timestamp": timestamp,
            "status": "excluded_medium_confidence",
        }
        await async_db.retraining_uncertain_pool.replace_one({"_id": uncertain_id}, doc, upsert=True)
        return {
            "confidence_filter_status": "excluded_medium_confidence",
            "allow_for_gan": False,
            "verified_by_human": False,
            "review_queue_id": None,
            "uncertain_pool_id": uncertain_id,
            "review_reason": None,
        }

    review_id = f"RVW-{uuid.uuid4().hex[:12].upper()}"
    doc = {
        "_id": review_id,
        "review_id": review_id,
        "inspection_id": inspection_id,
        "wafer_image": wafer_image,
        "model_prediction": model_prediction,
        "predicted_class": model_prediction,
        "confidence": round(confidence, 4),
        "timestamp": timestamp,
        "review_reason": "Low Confidence",
        "expert_label": None,
        "verified_label": None,
        "verification_status": False,
        "verified_by_human": False,
        "reviewed": False,
        "status": "pending_review",
        "eligible_for_gan": False,
    }
    await async_db.human_review_queue.replace_one({"_id": review_id}, doc, upsert=True)
    return {
        "confidence_filter_status": "pending_review",
        "allow_for_gan": False,
        "verified_by_human": False,
        "review_queue_id": review_id,
        "uncertain_pool_id": None,
        "review_reason": "Low Confidence",
    }


async def _load_review_queue_payload() -> Dict[str, Any]:
    queue = await async_db.human_review_queue.find({}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    uncertain = await async_db.retraining_uncertain_pool.find({}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    history = await _load_history()

    high_confidence_samples = 0
    for item in history:
        if not item.get("drift_detected"):
            continue
        defect_class = str(item.get("defect_class", "")).strip().lower()
        confidence = float(item.get("confidence", 0.0))
        if defect_class != "random" and confidence >= GAN_CONFIDENCE_THRESHOLD:
            high_confidence_samples += 1
    human_verified_samples = sum(1 for item in queue if item.get("verification_status"))
    awaiting_expert_review = sum(1 for item in queue if not item.get("verification_status"))

    return {
        "stats": {
            "high_confidence_samples": high_confidence_samples,
            "medium_confidence_samples": len(uncertain),
            "awaiting_expert_review": awaiting_expert_review,
            "human_verified_samples": human_verified_samples,
        },
        "queue": queue,
        "label_options": DEFECT_LABEL_OPTIONS,
    }


async def _get_review_queue_item(review_id: str) -> Dict[str, Any] | None:
    doc = await async_db.human_review_queue.find_one({"_id": review_id}, {"_id": 0})
    return doc

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="AutoYield AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    confidence_threshold: float = Form(0.45),
    max_low_confidence: int = Form(3),
    synth_trigger_mode: Literal["below", "above"] = Form("above"),
    synth_count: int = Form(10),
    synth_size: int = Form(64),
    auto_retrain: bool = Form(False),
    retrain_epochs: int = Form(1),
    min_accuracy_delta: float = Form(0.0),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    original_suffix = Path(file.filename).suffix.lower() if file.filename else ".png"
    safe_filename = f"{uuid.uuid4().hex}{original_suffix}"
    file_path = UPLOAD_DIR / safe_filename

    with open(file_path, "wb") as f:
        f.write(await file.read())

    start_time = time.time()

    defect_class, confidence, top_predictions = await asyncio.to_thread(
        predict_with_probs, str(file_path)
    )
    cam_class, cam_path = await asyncio.to_thread(generate_gradcam, str(file_path))
    heatmap_analysis = await asyncio.to_thread(summarize_gradcam_overlay, cam_path)

    drift_mon = get_drift_monitor(
        confidence_threshold=confidence_threshold,
        max_low_confidence=max_low_confidence,
        trigger_mode=synth_trigger_mode,
    )
    drift_detected = await asyncio.to_thread(drift_mon.update, confidence)

    triage_result = await asyncio.to_thread(
        triage,
        str(file_path),
        defect_class,
        confidence,
        top_predictions,
    )
    triage_result = {
        **triage_result,
        **heatmap_analysis,
        "priority": (
            "high"
            if drift_detected or confidence < 0.55 or heatmap_analysis.get("num_hotspots", 0) >= 4
            else "normal"
        ),
    }

    tool_name = os.getenv("AUTOYIELD_TOOL_NAME", "Litho-04")
    process_stage = os.getenv("AUTOYIELD_PROCESS_STAGE", "wafer-inspection")
    reasoning_context = {
        "prediction_class": defect_class,
        "confidence_score": round(confidence, 4),
        "drift_status": drift_detected,
        "heatmap_region": heatmap_analysis.get("dominant_region", "unknown"),
        "activation_spread": heatmap_analysis.get("spread_score", 0.0),
        "hotspot_count": heatmap_analysis.get("num_hotspots", 0),
        "inspection_tool": tool_name,
        "process_stage": process_stage,
    }
    reasoning = await asyncio.to_thread(analyze_defect, defect_class, confidence, reasoning_context)

    inspection_id = f"INS-{uuid.uuid4().hex[:12].upper()}"
    inspection_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wafer_image = _encode_image(file_path)
    filter_result = await _route_retraining_sample(
        inspection_id=inspection_id,
        timestamp=inspection_timestamp,
        confidence=confidence,
        model_prediction=defect_class,
        wafer_image=wafer_image,
    )

    synth_paths: List[str] = []
    if drift_detected and filter_result["allow_for_gan"]:
        synth_paths = await asyncio.to_thread(
            generate_synthetic_images,
            output_dir=str(SYNTH_DIR),
            num_images=synth_count,
            image_size=(synth_size, synth_size),
            defect_class=defect_class,
        )

    retrain_result: Dict[str, Any] | None = None
    if synth_paths and auto_retrain:
        # User requested to just schedule the background retrain
        schedule_status = trigger_retraining(min_drift_events=1)
        retrain_result = schedule_status

    inference_ms = int((time.time() - start_time) * 1000)

    history_entry = {
        "inspection_id": inspection_id,
        "timestamp": inspection_timestamp,
        "defect_class": defect_class,
        "confidence": round(confidence, 4),
        "top_predictions": top_predictions,
        "inference_time_ms": inference_ms,
        "drift_detected": drift_detected,
        "synth_trigger_mode": synth_trigger_mode,
        "triage": triage_result,
        "severity": reasoning.get("severity_assessment"),
        "cause_summary": reasoning.get("cause_summary"),
        "synthetic_count": len(synth_paths),
        "auto_retrain": auto_retrain,
        "retrain_result": retrain_result,
        "confidence_filter_status": filter_result["confidence_filter_status"],
        "allow_for_gan": filter_result["allow_for_gan"],
        "verified_by_human": filter_result["verified_by_human"],
        "review_queue_id": filter_result["review_queue_id"],
        "uncertain_pool_id": filter_result["uncertain_pool_id"],
        "review_reason": filter_result["review_reason"],
    }

    await _append_history(history_entry)

    recent_history = await _load_history()
    recent_history = list(reversed(recent_history[-5:]))
    model_metrics = await _load_model_metrics()

    # ── RAG-powered AI Insight (Step 5) ───────────────────────────────────────
    tool_name = os.getenv("AUTOYIELD_TOOL_NAME", "Litho-04")
    process_stage = os.getenv("AUTOYIELD_PROCESS_STAGE", "wafer-inspection")
    target_layer = os.getenv("AUTOYIELD_TARGET_LAYER", "M2_Cu")
    drift_state = drift_mon.state
    observation = {
        "prediction_label": defect_class,
        "confidence": round(confidence, 4),
        "severity": reasoning.get("severity_assessment"),
        "top_predictions": top_predictions,
        "heatmap_analysis": {
            "dominant_region": heatmap_analysis.get("dominant_region", "unknown"),
            "spread_score": heatmap_analysis.get("spread_score", 0.0),
            "num_hotspots": heatmap_analysis.get("num_hotspots", 0),
            "max_activation": heatmap_analysis.get("max_activation", 0.0),
        },
        "drift": {
            "drift_detected": drift_detected,
            "current_score": drift_state.get("drift_events", 0),
            "recent_drift_events": drift_state.get("drift_events", 0),
            "threshold": confidence_threshold,
            "trend": "rising" if drift_detected else "stable",
            "tool": tool_name,
        },
        "metadata": {
            "lot_id": inspection_id,
            "target_layer": target_layer,
            "inspection_tool": tool_name,
            "process_stage": process_stage,
            "capture_time": history_entry["timestamp"],
            "inspection_id": inspection_id,
            "inference_time_ms": inference_ms,
        },
        "recent_history": recent_history,
        "model_metrics": model_metrics,
    }

    ai_insight: Dict[str, Any] = {}
    try:
        ai_insight = await asyncio.to_thread(generate_explanation, observation, 5)
    except Exception as _e:
        ai_insight = {"error": str(_e), "fallback_used": True}

    response = {
        "inspection_id": inspection_id,
        "timestamp": history_entry["timestamp"],
        "defect_class": defect_class,
        "confidence": round(confidence, 4),
        "top_predictions": top_predictions,
        "inference_time_ms": inference_ms,
        "drift_detected": drift_detected,
        "synth_trigger_mode": synth_trigger_mode,
        "triage": triage_result,
        "heatmap_analysis": heatmap_analysis,
        "reasoning": reasoning,
        "explainability_analysis": ai_insight,
        "ai_insight": ai_insight,
        "input_image": wafer_image,
        "heatmap_image": _encode_image(Path(cam_path)),
        "synthetic_images": [_encode_image(Path(p)) for p in synth_paths[:8]],
        "auto_retrain": auto_retrain,
        "retrain_result": retrain_result,
        "confidence_filter_status": filter_result["confidence_filter_status"],
        "allow_for_gan": filter_result["allow_for_gan"],
        "verified_by_human": filter_result["verified_by_human"],
        "review_queue_id": filter_result["review_queue_id"],
        "uncertain_pool_id": filter_result["uncertain_pool_id"],
        "review_reason": filter_result["review_reason"],
    }

    return response


@app.get("/api/history")
async def get_history():
    return await _load_history()


@app.get("/api/metrics")
async def get_metrics():
    docs = await _load_history()
    summary = _compute_summary_metrics(docs)
    model_metrics = await _load_model_metrics()

    drift_mon = get_drift_monitor()
    
    # ── Manufacturing Analytics ───────────────────────────────────────
    queue = await async_db.human_review_queue.find({}, {"_id": 0}).to_list(1000)
    from api.services.manufacturing_metrics import manufacturing_engine
    mfg_metrics = manufacturing_engine.calculate_metrics(docs, queue)

    return {
        "summary": summary,
        "model_metrics": model_metrics,
        "drift_state": drift_mon.state,
        "manufacturing_analytics": mfg_metrics
    }


@app.post("/api/report")
async def generate_report(payload: Dict[str, Any]):
    report_bundle = await asyncio.to_thread(generate_visual_report, payload)
    return Response(
        content=report_bundle["pdf_bytes"],
        media_type=report_bundle.get("mime_type", "application/pdf"),
        headers={
            "Content-Disposition": f'attachment; filename="{report_bundle["filename"]}"'
        },
    )


from src.self_improvement.auto_retrainer import trigger_retraining, get_retrain_status
@app.post("/api/drift/reset")
def reset_drift():
    # Sync operation wrapper for thread-safe singleton
    get_drift_monitor().reset()
    return {"status": "drift counter reset"}

@app.get("/api/retrain/status")
def retrain_status():
    """Return current drift queue size and retraining readiness."""
    return get_retrain_status()


@app.get("/api/retrain/review-queue")
async def get_retrain_review_queue():
    return await _load_review_queue_payload()


@app.post("/api/retrain/review-queue/{review_id}/submit")
async def submit_review_label(review_id: str, payload: Dict[str, Any]):
    expert_label = str(payload.get("expert_label", "")).strip()
    if expert_label not in DEFECT_LABEL_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid expert label.")

    existing = await _get_review_queue_item(review_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Review item not found.")

    update_doc = {
        "expert_label": expert_label,
        "verified_label": expert_label,
        "verification_status": True,
        "verified_by_human": True,
        "reviewed": True,
        "status": "verified_by_expert",
        "eligible_for_gan": True,
        "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    await async_db.human_review_queue.update_one({"_id": review_id}, {"$set": update_doc})

    return {
        "status": "ok",
        "item": await _get_review_queue_item(review_id),
        "queue_payload": await _load_review_queue_payload(),
    }


@app.post("/api/retrain/review-queue/{review_id}/mark-reviewed")
async def mark_reviewed(review_id: str):
    existing = await _get_review_queue_item(review_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Review item not found.")

    update_doc = {
        "reviewed": True,
        "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if existing.get("verification_status"):
        update_doc["status"] = "verified_by_expert"

    await async_db.human_review_queue.update_one({"_id": review_id}, {"$set": update_doc})

    return {
        "status": "ok",
        "item": await _get_review_queue_item(review_id),
        "queue_payload": await _load_review_queue_payload(),
    }


@app.post("/api/retrain")
def schedule_retrain(min_drift_events: int = 1):
    """
    Trigger a background retraining run when enough drift events are queued.
    Pass min_drift_events as a query param to override the threshold.
    """
    return trigger_retraining(min_drift_events=min_drift_events)
