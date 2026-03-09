from __future__ import annotations

import threading
from typing import Any, Dict, Literal, Optional

TriggerMode = Literal["below", "above"]

DEFAULT_CONFIDENCE_THRESHOLD = 0.45
DEFAULT_MAX_MATCH_COUNT = 3
DEFAULT_TRIGGER_MODE: TriggerMode = "below"


class DriftMonitor:
    """
    Stateful threshold monitor backed by MongoDB (sync PyMongo).

    A trigger is emitted once when the streak of matching confidences reaches
    max_low_confidence. It re-arms after a non-matching confidence.
    """

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        max_low_confidence: int = DEFAULT_MAX_MATCH_COUNT,
        trigger_mode: TriggerMode = DEFAULT_TRIGGER_MODE,
    ) -> None:
        self.confidence_threshold = float(confidence_threshold)
        self.max_low_confidence = int(max_low_confidence)
        self.trigger_mode: TriggerMode = trigger_mode
        self._lock = threading.Lock()
        self._state = self._load_state()
        self.configure(
            confidence_threshold=self.confidence_threshold,
            max_low_confidence=self.max_low_confidence,
            trigger_mode=self.trigger_mode,
        )

    def _default_state(self) -> Dict[str, Any]:
        return {
            "match_count": 0,
            "total_updates": 0,
            "drift_events": 0,
            "trigger_armed": True,
            "last_threshold": self.confidence_threshold,
            "last_trigger_mode": self.trigger_mode,
            "last_confidence": None,
        }

    def _load_state(self) -> Dict[str, Any]:
        try:
            from config.db import sync_db
            doc = sync_db["drift_state"].find_one({"_id": "singleton"})
            if doc and isinstance(doc, dict):
                # Migrate old key name if present
                if "match_count" not in doc and "low_confidence_count" in doc:
                    doc["match_count"] = int(doc.get("low_confidence_count", 0))
                merged = self._default_state()
                merged.update({k: v for k, v in doc.items() if k != "_id"})
                return merged
        except Exception:
            pass
        return self._default_state()

    def _save_state(self) -> None:
        try:
            from config.db import sync_db
            sync_db["drift_state"].update_one(
                {"_id": "singleton"},
                {"$set": self._state},
                upsert=True
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def configure(
        self,
        confidence_threshold: float,
        max_low_confidence: int,
        trigger_mode: TriggerMode,
    ) -> None:
        if max_low_confidence < 1:
            raise ValueError("max_low_confidence must be >= 1")
        if trigger_mode not in {"below", "above"}:
            raise ValueError("trigger_mode must be 'below' or 'above'")

        config_changed = (
            float(confidence_threshold) != float(self.confidence_threshold)
            or int(max_low_confidence) != int(self.max_low_confidence)
            or trigger_mode != self.trigger_mode
        )

        self.confidence_threshold = float(confidence_threshold)
        self.max_low_confidence = int(max_low_confidence)
        self.trigger_mode = trigger_mode
        self._state["last_threshold"] = self.confidence_threshold
        self._state["last_trigger_mode"] = self.trigger_mode
        if config_changed:
            self._state["match_count"] = 0
            self._state["trigger_armed"] = True
        self._save_state()

    def _is_match(self, confidence: float) -> bool:
        if self.trigger_mode == "below":
            return confidence < self.confidence_threshold
        return confidence > self.confidence_threshold

    def update(self, confidence: float) -> bool:
        with self._lock:
            self._state["total_updates"] = int(self._state.get("total_updates", 0)) + 1
            self._state["last_confidence"] = float(confidence)
            self._state["last_threshold"] = self.confidence_threshold
            self._state["last_trigger_mode"] = self.trigger_mode

            if self._is_match(confidence):
                self._state["match_count"] = int(self._state.get("match_count", 0)) + 1
            else:
                self._state["match_count"] = 0
                self._state["trigger_armed"] = True
                self._save_state()
                return False

            trigger_ready = (
                bool(self._state.get("trigger_armed", True))
                and int(self._state["match_count"]) >= self.max_low_confidence
            )
            if trigger_ready:
                self._state["drift_events"] = int(self._state.get("drift_events", 0)) + 1
                self._state["trigger_armed"] = False
                self._save_state()
                return True

            self._save_state()
            return False

    def reset(self) -> None:
        with self._lock:
            self._state["match_count"] = 0
            self._state["trigger_armed"] = True
            self._save_state()

    @property
    def low_confidence_count(self) -> int:
        return int(self._state.get("match_count", 0))

    @property
    def state(self) -> Dict[str, Any]:
        payload = dict(self._state)
        payload["low_confidence_count"] = int(payload.get("match_count", 0))
        return payload


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

_singleton_lock = threading.Lock()
_singleton: DriftMonitor | None = None


def get_drift_monitor(
    confidence_threshold: Optional[float] = None,
    max_low_confidence: Optional[int] = None,
    trigger_mode: Optional[TriggerMode] = None,
) -> DriftMonitor:
    """Return process-level DriftMonitor singleton."""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = DriftMonitor(
                confidence_threshold=(
                    DEFAULT_CONFIDENCE_THRESHOLD
                    if confidence_threshold is None
                    else confidence_threshold
                ),
                max_low_confidence=(
                    DEFAULT_MAX_MATCH_COUNT
                    if max_low_confidence is None
                    else max_low_confidence
                ),
                trigger_mode=(
                    DEFAULT_TRIGGER_MODE if trigger_mode is None else trigger_mode
                ),
            )
        elif (
            confidence_threshold is not None
            or max_low_confidence is not None
            or trigger_mode is not None
        ):
            _singleton.configure(
                confidence_threshold=(
                    _singleton.confidence_threshold
                    if confidence_threshold is None
                    else confidence_threshold
                ),
                max_low_confidence=(
                    _singleton.max_low_confidence
                    if max_low_confidence is None
                    else max_low_confidence
                ),
                trigger_mode=(
                    _singleton.trigger_mode if trigger_mode is None else trigger_mode
                ),
            )

        return _singleton
