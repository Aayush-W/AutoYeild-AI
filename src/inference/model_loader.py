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

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0
from src.models.convnext_model import ConvNeXtDefectClassifier

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = APP_ROOT / "models" / "baseline_model_finetuned.pt"
OLD_MODEL_PATH     = APP_ROOT / "models" / "baseline_model.pt"
DEFAULT_CLASSES_JSON = APP_ROOT / "models" / "classes.json"


def _compute_file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    if not path.exists():
        return "not_found"
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_model_and_classes(
    model_path: str | os.PathLike = DEFAULT_MODEL_PATH,
) -> Tuple[nn.Module, List[str], Dict[str, str]]:
    """
    Dynamically load the classifier based on checkpoint metadata.
    Supports: EfficientNet-B0 and ConvNeXt-Small.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_path = Path(model_path)
    # If the finetuned model doesn't exist yet, fall back to the old one
    if not model_path.exists() and model_path == DEFAULT_MODEL_PATH:
        model_path = OLD_MODEL_PATH

    if not model_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found at {model_path}")

    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # 1. Load Classes
    ckpt_classes: List[str] = checkpoint.get("class_names", [])
    classes_json = (
        DEFAULT_CLASSES_JSON
        if model_path == DEFAULT_MODEL_PATH or model_path == OLD_MODEL_PATH
        else model_path.with_name("classes.json")
    )
    if classes_json.exists():
        data = json.loads(classes_json.read_text())
        class_names = data.get("classes", []) or ckpt_classes
    else:
        class_names = ckpt_classes

    num_classes = len(class_names)
    if not class_names:
        raise ValueError("Could not determine class names from checkpoint or JSON.")

    # 2. Determine Architecture
    model_type = checkpoint.get("model_type", "efficientnet_b0")
    
    if model_type == "convnext_small":
        from src.models.convnext_model import ConvNeXtDefectClassifier
        model = ConvNeXtDefectClassifier(num_classes=num_classes, pretrained=False)
    else:
        model = efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)

    # 3. Load Weights
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict)
    model = model.to(device)
    model.eval()

    stat = model_path.stat()
    meta = {
        "model_path": str(model_path),
        "model_type": model_type,
        "model_mtime": str(stat.st_mtime),
        "model_sha256": _compute_file_sha256(model_path),
        "classes_source": "classes.json" if classes_json.exists() else "checkpoint",
    }

    return model, class_names, meta


# ---------------------------------------------------------------------------
# Module-level singleton — loaded once on first import
# ---------------------------------------------------------------------------
_singleton: tuple | None = None
_cache_lock = threading.Lock()

def get_default_model():
    """
    Return (model, class_names, meta) for the default checkpoint.
    Loaded only on the first call; all subsequent calls return the cached objects.
    """
    global _singleton
    with _cache_lock:
        if _singleton is None:
            _singleton = load_model_and_classes(DEFAULT_MODEL_PATH)
        return _singleton

def invalidate_cache(model_path: str | Path | None = None) -> None:
    """Remove a cached model so the next call reloads from disk (e.g. after retraining)."""
    global _singleton
    with _cache_lock:
        _singleton = None
