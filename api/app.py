# Load .env variables FIRST — before any module reads os.getenv()
from dotenv import load_dotenv
load_dotenv()

import asyncio
import base64
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from src.inference.run_inference import predict_with_probs
from src.inference.gradcam import generate_gradcam
from src.reasoning.root_cause_agent import analyze_defect
from src.autonomy.drift_monitor import get_drift_monitor
from src.autonomy.triage_agent import triage
from src.self_improvement.synthetic_generator import generate_synthetic_images

from config.db import async_db
from api.services.insight_reasoner import generate_ai_insight

APP_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = APP_ROOT / "outputs" / "uploads"
SYNTH_DIR = APP_ROOT / "outputs" / "synthetic_images"

# ---------------------------------------------------------------------------
# Lifespan: warm up drift monitor singleton on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
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

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="AutoYield AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
    reasoning = await asyncio.to_thread(analyze_defect, defect_class, confidence)

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

    synth_paths: List[str] = []
    if drift_detected:
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
    inspection_id = f"INS-{uuid.uuid4().hex[:12].upper()}"

    history_entry = {
        "inspection_id": inspection_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    }

    await _append_history(history_entry)

    # ── RAG-powered AI Insight (Step 5) ───────────────────────────────────────
    drift_state = drift_mon.state
    observation = {
        "prediction_label": defect_class,
        "confidence": round(confidence, 4),
        "heatmap_analysis": {
            "dominant_region": triage_result.get("dominant_region", "unknown")
                if isinstance(triage_result, dict) else "unknown",
            "spread_score":    triage_result.get("spread_score", 0.0)
                if isinstance(triage_result, dict) else 0.0,
            "num_hotspots":    triage_result.get("num_hotspots", 0)
                if isinstance(triage_result, dict) else 0,
            "max_activation":  triage_result.get("max_activation", 0.0)
                if isinstance(triage_result, dict) else 0.0,
        },
        "drift": {
            "current_score": drift_state.get("drift_events", 0),
            "trend":         "rising" if drift_detected else "stable",
            "tool":          "inspection-tool",
        },
        "metadata": {
            "lot_id":        inspection_id,
            "process_stage": "wafer-inspection",
        },
    }

    ai_insight: Dict[str, Any] = {}
    try:
        ai_insight = await asyncio.to_thread(generate_ai_insight, observation, 5)
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
        "reasoning": reasoning,
        "ai_insight": ai_insight,
        "input_image": _encode_image(file_path),
        "heatmap_image": _encode_image(Path(cam_path)),
        "synthetic_images": [_encode_image(Path(p)) for p in synth_paths[:8]],
        "auto_retrain": auto_retrain,
        "retrain_result": retrain_result,
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
    return {
        "summary": summary,
        "model_metrics": model_metrics,
        "drift_state": drift_mon.state,
    }


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


@app.post("/api/retrain")
def schedule_retrain(min_drift_events: int = 1):
    """
    Trigger a background retraining run when enough drift events are queued.
    Pass min_drift_events as a query param to override the threshold.
    """
    return trigger_retraining(min_drift_events=min_drift_events)
