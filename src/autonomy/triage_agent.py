"""
Active-learning triage agent for AutoYield-AI.

Identifies uncertain or novel predictions that should be reviewed by a human
and queued for inclusion in the next retraining cycle.

Triage criteria (either is sufficient to queue):
1. Confidence is below *confidence_threshold* (model is unsure).
2. Top-2 softmax probabilities are within *ambiguity_margin* of each other
   (model is roughly split between two classes — ambiguous / potentially novel).

Usage
-----
from src.autonomy.triage_agent import triage

result = triage(
    image_path="outputs/uploads/wafer_001.png",
    predicted_class="Edge ring",
    confidence=0.38,
    top_predictions=[{"label": "Edge ring", "prob": 0.38}, {"label": "Local", "prob": 0.34}],
)
# result = {"queued": True, "reason": "low_confidence", "entry_id": "RT-..."}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.self_improvement.auto_retrainer import queue_for_retraining


def triage(
    image_path: str,
    predicted_class: str,
    confidence: float,
    top_predictions: Optional[List[Dict[str, Any]]] = None,
    confidence_threshold: float = 0.55,
    ambiguity_margin: float = 0.10,
) -> Dict[str, Any]:
    """
    Decide whether to queue *image_path* for human review.

    Parameters
    ----------
    image_path:
        Absolute path to the image being analyzed.
    predicted_class:
        Raw model label for the top-1 prediction.
    confidence:
        Softmax probability of the top-1 prediction.
    top_predictions:
        List of {"label": str, "prob": float} from predict_with_probs().
        Used to detect ambiguity between the top two classes.
    confidence_threshold:
        Samples below this confidence are always queued.
    ambiguity_margin:
        If |top-1 prob − top-2 prob| < margin the case is queued as ambiguous.

    Returns
    -------
    dict with keys:
        queued   – bool
        reason   – str  ('low_confidence', 'ambiguous', or 'accepted')
        entry_id – str (present only when queued=True)
    """
    # Check 1: low confidence
    if confidence < confidence_threshold:
        entry = queue_for_retraining(
            image_path=image_path,
            predicted_class=predicted_class,
            confidence=confidence,
            reason="low_confidence",
        )
        return {"queued": True, "reason": "low_confidence", "entry_id": entry["entry_id"]}

    # Check 2: ambiguity between top two predictions
    if top_predictions and len(top_predictions) >= 2:
        prob_1 = float(top_predictions[0].get("prob", 1.0))
        prob_2 = float(top_predictions[1].get("prob", 0.0))
        if (prob_1 - prob_2) < ambiguity_margin:
            entry = queue_for_retraining(
                image_path=image_path,
                predicted_class=predicted_class,
                confidence=confidence,
                reason="ambiguous",
            )
            return {
                "queued": True,
                "reason": "ambiguous",
                "entry_id": entry["entry_id"],
            }

    return {"queued": False, "reason": "accepted"}
