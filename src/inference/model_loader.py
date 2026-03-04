"""
Shared model loading utility for AutoYield-AI.

Provides a single, cached load_model() to avoid duplicated checkpoint loading
across run_inference.py, gradcam.py, and any future modules.

Usage
-----
from src.inference.model_loader import load_model

model, class_names, device = load_model()
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODEL_PATH = _PROJECT_ROOT / "models" / "baseline_model.pt"

# Module-level cache: path → (model, class_names, device)
_cache: Dict[str, Tuple[nn.Module, List[str], str]] = {}
_cache_lock = threading.Lock()


def load_model(
    model_path: str | Path | None = None,
    device: str | None = None,
) -> Tuple[nn.Module, List[str], str]:
    """
    Load (and cache) an EfficientNet-B0 checkpoint.

    Parameters
    ----------
    model_path:
        Path to the .pt checkpoint.  Defaults to models/baseline_model.pt.
    device:
        'cuda' or 'cpu'.  Auto-detected if not provided.

    Returns
    -------
    (model, class_names, device)
        model      – nn.Module in eval() mode
        class_names – ordered list of class label strings
        device     – the device string the model is on
    """
    resolved_path = str(Path(model_path) if model_path else _DEFAULT_MODEL_PATH)
    resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    cache_key = f"{resolved_path}::{resolved_device}"

    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key]

        if not Path(resolved_path).exists():
            raise FileNotFoundError(
                f"Model checkpoint not found: {resolved_path}\n"
                "Run `python src/training/train_classifier.py` first."
            )

        checkpoint = torch.load(resolved_path, map_location=resolved_device)
        class_names: List[str] = checkpoint["class_names"]
        num_classes = len(class_names)

        net = efficientnet_b0(weights=None)
        in_features = net.classifier[1].in_features
        net.classifier[1] = nn.Linear(in_features, num_classes)
        net.load_state_dict(checkpoint["model_state_dict"])
        net = net.to(resolved_device)
        net.eval()

        _cache[cache_key] = (net, class_names, resolved_device)
        return _cache[cache_key]


def invalidate_cache(model_path: str | Path | None = None) -> None:
    """Remove a cached model so the next call reloads from disk (e.g. after retraining)."""
    with _cache_lock:
        if model_path is None:
            _cache.clear()
        else:
            key_prefix = str(Path(model_path))
            keys_to_remove = [k for k in _cache if k.startswith(key_prefix)]
            for k in keys_to_remove:
                del _cache[k]
