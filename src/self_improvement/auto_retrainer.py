"""
Auto-retraining queue and trigger for AutoYield-AI.

Provides three functions:
1. queue_for_retraining()  — appends an uncertain/novel sample to the retraining queue JSON.
2. check_retraining_threshold() — returns True when the queue has enough entries.
3. trigger_retraining()    — stub that logs intent and returns a status dict.
                              Wire this to a subprocess / celery task in production.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_QUEUE_FILE = _PROJECT_ROOT / "outputs" / "metrics" / "retraining_queue.json"
_QUEUE_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_queue() -> list[Dict[str, Any]]:
    if _QUEUE_FILE.exists():
        try:
            data = json.loads(_QUEUE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _save_queue(queue: list[Dict[str, Any]]) -> None:
    _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def queue_for_retraining(
    image_path: str,
    predicted_class: str,
    confidence: float,
    reason: str = "low_confidence",
) -> Dict[str, Any]:
    """
    Append an entry to the retraining queue.

    Parameters
    ----------
    image_path:    Absolute path to the image that needs human review.
    predicted_class: Raw model prediction label.
    confidence:    Model confidence score.
    reason:        Why this sample was queued ('low_confidence', 'ambiguous', etc.)

    Returns
    -------
    The newly created queue entry dict.
    """
    entry: Dict[str, Any] = {
        "entry_id": f"RT-{uuid.uuid4().hex[:10].upper()}",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "image_path": str(image_path),
        "predicted_class": predicted_class,
        "confidence": round(confidence, 4),
        "reason": reason,
        "status": "pending",  # pending → reviewed → trained
    }
    with _QUEUE_LOCK:
        queue = _load_queue()
        queue.append(entry)
        _save_queue(queue)
    return entry


def check_retraining_threshold(min_queue_size: int = 50) -> bool:
    """
    Return True if the pending retraining queue has >= *min_queue_size* entries.
    """
    with _QUEUE_LOCK:
        queue = _load_queue()
    pending = [e for e in queue if e.get("status") == "pending"]
    return len(pending) >= min_queue_size


def trigger_retraining(model_path: str | None = None) -> Dict[str, Any]:
    """
    Request a retraining run.

    Currently a stub — logs the request and returns a status dict.
    In production, replace the body with a subprocess call to
    `python src/training/train_classifier.py` or a Celery task dispatch.

    Returns a status dict with keys: triggered, message, queue_size.
    """
    with _QUEUE_LOCK:
        queue = _load_queue()
        pending = [e for e in queue if e.get("status") == "pending"]
        queue_size = len(pending)

    # Mark all pending entries as "triggered"
    with _QUEUE_LOCK:
        full_queue = _load_queue()
        for entry in full_queue:
            if entry.get("status") == "pending":
                entry["status"] = "triggered"
        _save_queue(full_queue)

    status = {
        "triggered": True,
        "message": (
            f"Retraining queued for {queue_size} samples. "
            "Connect a subprocess / Celery worker to run train_classifier.py automatically."
        ),
        "queue_size": queue_size,
        "model_path": str(model_path) if model_path else "models/baseline_model.pt",
    }
    return status
