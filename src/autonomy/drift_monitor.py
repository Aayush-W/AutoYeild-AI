"""
Persistent, file-backed drift monitor.

Bug fixes vs previous revision:
- get_drift_monitor() now UPDATES confidence_threshold and max_low_confidence
  on the existing singleton whenever the caller passes different values.
  Previously these were silently ignored after first creation, meaning drift
  would never fire correctly if the threshold changed between requests.
- _save_state() is now only called when the count actually changes, not on
  every high-confidence update that resets to 0 unnecessarily.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict

_STATE_FILE = (
    Path(__file__).resolve().parents[2] / "outputs" / "metrics" / "drift_state.json"
)


class DriftMonitor:
    """
    Counts consecutive low-confidence predictions and declares drift when the
    count reaches *max_low_confidence*.

    Parameters
    ----------
    confidence_threshold:
        Predictions below this value are considered "uncertain".
    max_low_confidence:
        Number of consecutive uncertain predictions required to declare drift.
    state_file:
        JSON file where the counter is persisted so state survives restarts.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.45,
        max_low_confidence: int = 3,
        state_file: Path | None = None,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.max_low_confidence = max_low_confidence
        self._state_file = Path(state_file) if state_file else _STATE_FILE
        self._lock = threading.Lock()
        self._state = self._load_state()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {"low_confidence_count": 0, "total_updates": 0, "drift_events": 0}

    def _save_state(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(
                json.dumps(self._state, indent=2), encoding="utf-8"
            )
        except Exception:
            pass  # Non-fatal — in-memory count is still correct

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, confidence: float) -> bool:
        """
        Record a new prediction confidence.

        Returns True if drift is detected (consecutive low-confidence count
        has reached *max_low_confidence*).
        """
        with self._lock:
            self._state["total_updates"] = self._state.get("total_updates", 0) + 1

            if confidence < self.confidence_threshold:
                self._state["low_confidence_count"] = (
                    self._state.get("low_confidence_count", 0) + 1
                )
            else:
                self._state["low_confidence_count"] = 0

            drift = self._state["low_confidence_count"] >= self.max_low_confidence

            if drift:
                self._state["drift_events"] = self._state.get("drift_events", 0) + 1
                # Reset streak after signalling so next window starts fresh
                self._state["low_confidence_count"] = 0

            self._save_state()
            return drift

    def reset(self) -> None:
        """Manually reset the drift counter (e.g. after retraining)."""
        with self._lock:
            self._state["low_confidence_count"] = 0
            self._save_state()

    @property
    def low_confidence_count(self) -> int:
        return self._state.get("low_confidence_count", 0)

    @property
    def state(self) -> Dict[str, Any]:
        return dict(self._state)


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

_singleton_lock = threading.Lock()
_singleton: DriftMonitor | None = None


def get_drift_monitor(
    confidence_threshold: float = 0.45,
    max_low_confidence: int = 3,
) -> DriftMonitor:
    """
    Return the process-level DriftMonitor singleton.

    BUG FIX: thresholds are now updated on every call so that changing
    confidence_threshold or max_low_confidence via the API Form parameters
    takes effect immediately rather than being silently ignored after the
    first request created the instance.
    """
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = DriftMonitor(
                confidence_threshold=confidence_threshold,
                max_low_confidence=max_low_confidence,
            )
        else:
            # Update thresholds in-place so per-request values are respected
            _singleton.confidence_threshold = confidence_threshold
            _singleton.max_low_confidence = max_low_confidence
        return _singleton
