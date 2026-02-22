import base64
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from src.inference.run_inference import predict_with_probs
from src.inference.gradcam import generate_gradcam
from src.reasoning.root_cause_agent import analyze_defect
from src.autonomy.drift_monitor import DriftMonitor
from src.self_improvement.synthetic_generator import generate_synthetic_images


APP_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = APP_ROOT / "outputs" / "uploads"
SYNTH_DIR = APP_ROOT / "outputs" / "synthetic_images"
METRICS_DIR = APP_ROOT / "outputs" / "metrics"
HISTORY_FILE = METRICS_DIR / "inspections.json"
MODEL_METRICS_FILE = METRICS_DIR / "model_metrics.json"


def _encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    ext = path.suffix.lower().replace(".", "") or "png"
    return f"data:image/{ext};base64,{data}"


def _load_history() -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def _save_history(history: List[Dict[str, Any]]) -> None:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def _append_history(entry: Dict[str, Any]) -> None:
    history = _load_history()
    history.append(entry)
    history = history[-200:]
    _save_history(history)


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


def _load_model_metrics() -> Dict[str, Any]:
    if not MODEL_METRICS_FILE.exists():
        return {}
    try:
        return json.loads(MODEL_METRICS_FILE.read_text())
    except Exception:
        return {}


app = FastAPI(title="AutoYield AI API", version="1.0.0")

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
    max_low_confidence: int = Form(1),
    synth_count: int = Form(10),
    synth_size: int = Form(64),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as f:
        f.write(await file.read())

    start_time = time.time()
    
    # Run CPU-bound inference in a separate thread to avoid blocking the async event loop
    defect_class, confidence, top_predictions = await asyncio.to_thread(predict_with_probs, str(file_path))
    cam_class, cam_path = await asyncio.to_thread(generate_gradcam, str(file_path))
    reasoning = await asyncio.to_thread(analyze_defect, defect_class, confidence)

    drift_monitor = DriftMonitor(
        confidence_threshold=confidence_threshold,
        max_low_confidence=max_low_confidence,
    )
    drift_detected = await asyncio.to_thread(drift_monitor.update, confidence)

    synth_paths = []
    if drift_detected:
        synth_paths = await asyncio.to_thread(
            generate_synthetic_images,
            output_dir=str(SYNTH_DIR),
            num_images=synth_count,
            image_size=(synth_size, synth_size),
        )

    inference_ms = int((time.time() - start_time) * 1000)

    history_entry = {
        "inspection_id": f"INS-{int(time.time())}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "defect_class": defect_class,
        "confidence": round(confidence, 4),
        "top_predictions": top_predictions,
        "inference_time_ms": inference_ms,
        "drift_detected": drift_detected,
        "severity": reasoning.get("severity_assessment"),
        "cause_summary": reasoning.get("cause_summary"),
        "synthetic_count": len(synth_paths),
    }
    _append_history(history_entry)

    response = {
        "inspection_id": history_entry["inspection_id"],
        "timestamp": history_entry["timestamp"],
        "defect_class": defect_class,
        "confidence": round(confidence, 4),
        "top_predictions": top_predictions,
        "inference_time_ms": inference_ms,
        "drift_detected": drift_detected,
        "reasoning": reasoning,
        "input_image": _encode_image(file_path),
        "heatmap_image": _encode_image(Path(cam_path)),
        "synthetic_images": [_encode_image(Path(p)) for p in synth_paths[:8]],
    }

    return response


@app.get("/api/history")
def get_history():
    return _load_history()


@app.get("/api/metrics")
def get_metrics():
    history = _load_history()
    summary = _compute_summary_metrics(history)
    model_metrics = _load_model_metrics()
    return {
        "summary": summary,
        "model_metrics": model_metrics,
    }
