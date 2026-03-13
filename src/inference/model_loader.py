"""
Shared model loading utility for AutoYield-AI.

Supports the runtime checkpoints currently used by the app. The baseline path
may now point to either an EfficientNet-B0 or ConvNeXt checkpoint, while older
EfficientNet-only training code remains unchanged elsewhere.
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
from torchvision.models import convnext_base, convnext_small, convnext_tiny, efficientnet_b0

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = APP_ROOT / "models" / "baseline_model.pt"
DEFAULT_CLASSES_JSON = APP_ROOT / "models" / "classes.json"

SUPPORTED_MODEL_BUILDERS = {
    "efficientnet_b0": efficientnet_b0,
    "convnext_tiny": convnext_tiny,
    "convnext_small": convnext_small,
    "convnext_base": convnext_base,
}


def _compute_file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _build_model(model_type: str, num_classes: int) -> nn.Module:
    builder = SUPPORTED_MODEL_BUILDERS.get(model_type)
    if builder is None:
        supported = ", ".join(sorted(SUPPORTED_MODEL_BUILDERS))
        raise ValueError(f"Unsupported model_type '{model_type}'. Supported: {supported}")

    model = builder(weights=None)
    if model_type.startswith("efficientnet"):
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
    elif model_type.startswith("convnext"):
        in_features = model.classifier[2].in_features
        model.classifier[2] = nn.Linear(in_features, num_classes)
    else:
        raise ValueError(f"Unsupported model_type '{model_type}'")

    return model


def get_gradcam_target_layer(model: nn.Module, model_type: str) -> nn.Module:
    if model_type.startswith("efficientnet"):
        return model.features[-1]
    if model_type.startswith("convnext"):
        return model.features[-1][-1].block[0]
    raise ValueError(f"No Grad-CAM target layer configured for model_type '{model_type}'")


def load_model_and_classes(
    model_path: str | os.PathLike = DEFAULT_MODEL_PATH,
) -> Tuple[nn.Module, List[str], Dict[str, str]]:
    """
    Load EfficientNet-B0 model and class mapping used across training and inference.

    - Prefers classes from classes.json (written by the trainer)
    - Falls back to checkpoint['class_names'] if JSON does not exist
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_path = Path(model_path)
    if not model_path.is_absolute():
        model_path = (APP_ROOT / model_path).resolve()

    checkpoint = torch.load(model_path, map_location=device)
    if not isinstance(checkpoint, dict):
        raise TypeError(f"Unsupported checkpoint format in '{model_path}'")

    ckpt_classes: List[str] = checkpoint.get("class_names", [])
    model_type = checkpoint.get("model_type", "efficientnet_b0")
    state_dict = checkpoint.get("model_state_dict")
    if state_dict is None:
        raise KeyError(f"Checkpoint '{model_path}' is missing 'model_state_dict'")

    # Prefer classes.json; fall back to checkpoint
    classes_json = (
        DEFAULT_CLASSES_JSON
        if model_path == DEFAULT_MODEL_PATH
        else model_path.with_name("classes.json")
    )
    if classes_json.exists():
        data = json.loads(classes_json.read_text())
        json_classes: List[str] = data.get("classes", [])
        class_names = json_classes or ckpt_classes
    else:
        class_names = ckpt_classes

    num_classes = len(class_names)
    if num_classes == 0:
        raise ValueError(f"No classes found for checkpoint '{model_path}'")

    model = _build_model(model_type, num_classes)
    model.load_state_dict(state_dict)
    model = model.to(device)
    model.eval()

    stat = model_path.stat()
    meta = {
        "model_path": str(model_path),
        "model_mtime": str(stat.st_mtime),
        "model_sha256": _compute_file_sha256(model_path),
        "model_type": model_type,
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
