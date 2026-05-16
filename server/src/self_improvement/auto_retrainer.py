"""
auto_retrainer.py

Retraining trigger with confidence filtering safeguards.

Only samples that are either:
- high-confidence non-random predictions (>= 0.50), or
- verified by a human expert

are eligible to enter the GAN / retraining input stage.
"""
from __future__ import annotations

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
TRAINING_SCRIPT = APP_ROOT / "src" / "training" / "train_classifier.py"
GAN_CONFIDENCE_THRESHOLD = 0.50
HUMAN_REVIEW_THRESHOLD = 0.30
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


def _load_history() -> List[Dict[str, Any]]:
    return list(sync_db["inspections"].find({}, {"_id": 0}))


def _load_human_review_queue() -> List[Dict[str, Any]]:
    return list(
        sync_db["human_review_queue"].find({}, {"_id": 0}).sort("timestamp", -1)
    )


def _load_uncertain_pool() -> List[Dict[str, Any]]:
    return list(
        sync_db["retraining_uncertain_pool"].find({}, {"_id": 0}).sort("timestamp", -1)
    )


def _high_confidence_samples(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    high_confidence: List[Dict[str, Any]] = []
    for item in history:
        if not item.get("drift_detected"):
            continue
        predicted_class = str(item.get("defect_class", "")).strip().lower()
        confidence = float(item.get("confidence", 0.0))
        if predicted_class != "random" and confidence >= GAN_CONFIDENCE_THRESHOLD:
            high_confidence.append(item)
    return high_confidence


def _verified_human_samples(queue_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        item
        for item in queue_items
        if item.get("verification_status") is True
    ]


def _gan_eligible_samples(history: List[Dict[str, Any]], queue_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    eligible: List[Dict[str, Any]] = []

    for item in _high_confidence_samples(history):
        eligible.append(
            {
                "inspection_id": item.get("inspection_id"),
                "confidence": float(item.get("confidence", 0.0)),
                "verified_by_human": False,
                "predicted_class": item.get("defect_class"),
                "label": item.get("defect_class"),
                "source": "high_confidence_prediction",
            }
        )

    for item in _verified_human_samples(queue_items):
        eligible.append(
            {
                "inspection_id": item.get("inspection_id"),
                "confidence": float(item.get("confidence", 0.0)),
                "verified_by_human": True,
                "predicted_class": item.get("model_prediction"),
                "label": item.get("verified_label") or item.get("expert_label") or item.get("model_prediction"),
                "source": "human_verified_queue",
            }
        )

    return eligible


def _build_filtering_stats(
    history: List[Dict[str, Any]],
    queue_items: List[Dict[str, Any]],
    uncertain_pool: List[Dict[str, Any]],
) -> Dict[str, Any]:
    high_conf = _high_confidence_samples(history)
    verified = _verified_human_samples(queue_items)
    pending = [item for item in queue_items if not item.get("verification_status")]
    return {
        "high_confidence_samples": len(high_conf),
        "medium_confidence_samples": len(uncertain_pool),
        "awaiting_expert_review": len(pending),
        "human_verified_samples": len(verified),
    }


def get_retrain_status() -> Dict[str, Any]:
    history = _load_history()
    drift_events = [item for item in history if item.get("drift_detected")]
    latest = drift_events[-1] if drift_events else None
    queue_items = _load_human_review_queue()
    uncertain_pool = _load_uncertain_pool()
    eligible_samples = _gan_eligible_samples(history, queue_items)
    return {
        "drift_queue_size": len(drift_events),
        "latest_trigger": latest,
        "training_script_exists": TRAINING_SCRIPT.exists(),
        "confidence_filter_stats": _build_filtering_stats(history, queue_items, uncertain_pool),
        "gan_eligible_samples": len(eligible_samples),
        "label_options": DEFECT_LABEL_OPTIONS,
    }


def trigger_retraining(min_drift_events: int = 1) -> Dict[str, Any]:
    """
    Trigger a retraining run if there are enough drift events queued and the
    retraining input stage passes the confidence safety filter.
    """
    history = _load_history()
    drift_events = [item for item in history if item.get("drift_detected")]
    queue_items = _load_human_review_queue()
    eligible_samples = _gan_eligible_samples(history, queue_items)

    if len(drift_events) < min_drift_events:
        return {
            "triggered": False,
            "reason": f"Only {len(drift_events)} drift event(s) recorded; minimum required is {min_drift_events}.",
            "drift_queue_size": len(drift_events),
            "eligible_training_samples": len(eligible_samples),
        }

    try:
        assert all(
            sample["verified_by_human"]
            or (
                str(sample.get("predicted_class", "")).strip().lower() != "random"
                and sample["confidence"] >= GAN_CONFIDENCE_THRESHOLD
            )
            for sample in eligible_samples
        )
    except AssertionError:
        return {
            "triggered": False,
            "reason": "Retraining aborted: one or more samples failed the confidence or human-verification gate.",
            "drift_queue_size": len(drift_events),
            "eligible_training_samples": len(eligible_samples),
        }

    if not eligible_samples:
        return {
            "triggered": False,
            "reason": "Retraining aborted: no GAN-eligible samples are available after confidence filtering.",
            "drift_queue_size": len(drift_events),
            "eligible_training_samples": 0,
        }

    if not TRAINING_SCRIPT.exists():
        LOGGER.warning("Training script not found at %s", TRAINING_SCRIPT)
        return {
            "triggered": False,
            "reason": f"Training script not found at {TRAINING_SCRIPT}.",
            "drift_queue_size": len(drift_events),
            "eligible_training_samples": len(eligible_samples),
        }

    LOGGER.info(
        "Triggering retraining with %d drift event(s) and %d GAN-eligible sample(s).",
        len(drift_events),
        len(eligible_samples),
    )
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
            "eligible_training_samples": len(eligible_samples),
            "message": "Retraining process started in background.",
        }
    except Exception as exc:
        LOGGER.error("Failed to start training subprocess: %s", exc)
        return {
            "triggered": False,
            "reason": str(exc),
            "drift_queue_size": len(drift_events),
            "eligible_training_samples": len(eligible_samples),
        }
