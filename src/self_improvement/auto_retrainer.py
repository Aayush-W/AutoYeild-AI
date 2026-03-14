"""
auto_retrainer.py
Lightweight retraining trigger. Scans the inspections history for unacknowledged
drift events and kicks off a training run when a configurable threshold is met.
"""
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from config.db import sync_db

LOGGER = logging.getLogger("autoyield.retrainer")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)

APP_ROOT = Path(__file__).resolve().parents[2]
TRAINING_SCRIPT = APP_ROOT / "src" / "training" / "train_convnext_finetune.py"


def _load_history() -> List[Dict[str, Any]]:
    # Replaced JSON with MongoDB exact fetch!
    return list(sync_db["inspections"].find({}, {"_id": 0}))


def get_retrain_status() -> Dict[str, Any]:
    """Return current drift queue size and latest trigger info."""
    history = _load_history()
    drift_events = [item for item in history if item.get("drift_detected")]
    latest = drift_events[-1] if drift_events else None
    return {
        "drift_queue_size": len(drift_events),
        "latest_trigger": latest,
        "training_script_exists": TRAINING_SCRIPT.exists(),
    }


def trigger_retraining(min_drift_events: int = 1) -> Dict[str, Any]:
    """
    Trigger a retraining run if there are enough drift events queued.
    Returns a status dict describing what happened.
    """
    history = _load_history()
    drift_events = [item for item in history if item.get("drift_detected")]

    if len(drift_events) < min_drift_events:
        return {
            "triggered": False,
            "reason": f"Only {len(drift_events)} drift event(s) recorded; "
                      f"minimum required is {min_drift_events}.",
            "drift_queue_size": len(drift_events),
        }

    if not TRAINING_SCRIPT.exists():
        LOGGER.warning("Training script not found at %s", TRAINING_SCRIPT)
        return {
            "triggered": False,
            "reason": f"Training script not found at {TRAINING_SCRIPT}.",
            "drift_queue_size": len(drift_events),
        }

    LOGGER.info("Triggering retraining: %d drift event(s) in queue.", len(drift_events))
    try:
        proc = subprocess.Popen(
            [sys.executable, str(TRAINING_SCRIPT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return {
            "triggered": True,
            "pid": proc.pid,
            "drift_queue_size": len(drift_events),
            "message": "Retraining process started in background.",
        }
    except Exception as exc:
        LOGGER.error("Failed to start training subprocess: %s", exc)
        return {
            "triggered": False,
            "reason": str(exc),
            "drift_queue_size": len(drift_events),
        }
