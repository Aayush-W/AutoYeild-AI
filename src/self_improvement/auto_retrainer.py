from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_QUEUE_FILE = _PROJECT_ROOT / "outputs" / "metrics" / "retraining_queue.json"
_RETRAIN_METRICS_FILE = _PROJECT_ROOT / "outputs" / "metrics" / "retrain_metrics.json"
_QUEUE_LOCK = threading.Lock()


def _load_queue() -> List[Dict[str, Any]]:
    if _QUEUE_FILE.exists():
        try:
            data = json.loads(_QUEUE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _save_queue(queue: List[Dict[str, Any]]) -> None:
    _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")


def queue_for_retraining(
    image_path: str,
    predicted_class: str,
    confidence: float,
    reason: str = "low_confidence",
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "entry_id": f"RT-{uuid.uuid4().hex[:10].upper()}",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "image_path": str(image_path),
        "predicted_class": predicted_class,
        "confidence": round(confidence, 4),
        "reason": reason,
        "status": "pending",
    }
    with _QUEUE_LOCK:
        queue = _load_queue()
        queue.append(entry)
        _save_queue(queue)
    return entry


def check_retraining_threshold(min_queue_size: int = 50) -> bool:
    with _QUEUE_LOCK:
        queue = _load_queue()
    pending = [e for e in queue if e.get("status") == "pending"]
    return len(pending) >= min_queue_size


def trigger_retraining(model_path: str | None = None) -> Dict[str, Any]:
    with _QUEUE_LOCK:
        queue = _load_queue()
        pending = [e for e in queue if e.get("status") == "pending"]
        queue_size = len(pending)

    with _QUEUE_LOCK:
        full_queue = _load_queue()
        for entry in full_queue:
            if entry.get("status") == "pending":
                entry["status"] = "triggered"
        _save_queue(full_queue)

    return {
        "triggered": True,
        "message": (
            f"Retraining queued for {queue_size} samples. "
            "Connect this function to your offline training worker."
        ),
        "queue_size": queue_size,
        "model_path": str(model_path) if model_path else "models/baseline_model.pt",
    }


class _SyntheticDataset:
    def __init__(self, image_paths: List[str], class_idx: int, transform):
        self.image_paths = image_paths
        self.class_idx = class_idx
        self.transform = transform

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int):
        path = self.image_paths[idx]
        image = Image.open(path).convert("RGB")
        image = self.transform(image)
        return image, self.class_idx


class _MappedImageDataset:
    def __init__(self, samples: List[tuple[str, int]], transform):
        self.samples = samples
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        image = self.transform(image)
        return image, label


def _normalize_label(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def retrain_with_synthetic(
    synthetic_paths: List[str],
    target_class: str,
    epochs: int = 1,
    lr: float = 1e-4,
    min_accuracy_delta: float = 0.0,
    baseline_model_path: Optional[str] = None,
    updated_model_path: Optional[str] = None,
    val_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fine-tune classifier head on synthetic images for one class.
    Promote updated model only if validation accuracy is maintained/improved.
    """
    synthetic_paths = [p for p in synthetic_paths if Path(p).exists()]
    if not synthetic_paths:
        return {
            "retrained": False,
            "promoted": False,
            "reason": "No synthetic images available on disk.",
        }

    try:
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from sklearn.metrics import accuracy_score
        from torch.utils.data import DataLoader
        from torchvision import datasets, transforms
        from torchvision.models import efficientnet_b0
    except Exception as exc:
        return {
            "retrained": False,
            "promoted": False,
            "reason": f"Missing training dependencies: {exc}",
        }

    baseline_model = (
        Path(baseline_model_path)
        if baseline_model_path
        else (_PROJECT_ROOT / "models" / "baseline_model.pt")
    )
    updated_model = (
        Path(updated_model_path)
        if updated_model_path
        else (_PROJECT_ROOT / "models" / "updated_model.pt")
    )
    val_path = (
        Path(val_dir) if val_dir else (_PROJECT_ROOT / "data" / "processed" / "val")
    )

    if not baseline_model.exists():
        return {
            "retrained": False,
            "promoted": False,
            "reason": f"Baseline model not found: {baseline_model}",
        }
    if not val_path.exists():
        return {
            "retrained": False,
            "promoted": False,
            "reason": f"Validation data not found: {val_path}",
        }

    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoint = torch.load(str(baseline_model), map_location=device)
    class_names = list(checkpoint["class_names"])

    class_norm_to_idx = {_normalize_label(name): idx for idx, name in enumerate(class_names)}

    if _normalize_label(target_class) not in class_norm_to_idx:
        return {
            "retrained": False,
            "promoted": False,
            "reason": f"Target class '{target_class}' not in model classes {class_names}",
        }

    model = efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, len(class_names))
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)

    preprocess = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    val_dataset = datasets.ImageFolder(root=str(val_path), transform=preprocess)
    remapped_samples: List[tuple[str, int]] = []
    for sample_path, ds_idx in val_dataset.samples:
        ds_class = val_dataset.classes[ds_idx]
        norm_name = _normalize_label(ds_class)
        if norm_name in class_norm_to_idx:
            remapped_samples.append((sample_path, class_norm_to_idx[norm_name]))

    if not remapped_samples:
        return {
            "retrained": False,
            "promoted": False,
            "reason": (
                "Validation set has no classes mappable to model classes. "
                f"dataset={val_dataset.classes}, model={class_names}"
            ),
        }
    val_loader = DataLoader(
        _MappedImageDataset(remapped_samples, preprocess),
        batch_size=32,
        shuffle=False,
        num_workers=0,
    )

    def _evaluate_accuracy() -> float:
        model.eval()
        preds: List[int] = []
        targets: List[int] = []
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                outputs = model(images)
                predicted = outputs.argmax(dim=1).cpu().tolist()
                preds.extend(predicted)
                targets.extend(labels.tolist())
        return float(accuracy_score(targets, preds))

    before_acc = _evaluate_accuracy()

    # Train classifier head only for fast, bounded updates.
    for param in model.features.parameters():
        param.requires_grad = False
    for param in model.classifier.parameters():
        param.requires_grad = True

    target_idx = class_norm_to_idx[_normalize_label(target_class)]
    train_dataset = _SyntheticDataset(synthetic_paths, target_idx, preprocess)
    train_loader = DataLoader(
        train_dataset,
        batch_size=min(16, max(1, len(train_dataset))),
        shuffle=True,
        num_workers=0,
    )

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.classifier.parameters(), lr=lr)

    model.train()
    for _ in range(max(1, int(epochs))):
        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

    after_acc = _evaluate_accuracy()
    promoted = after_acc >= (before_acc + float(min_accuracy_delta))

    metrics_payload = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "target_class": target_class,
        "synthetic_samples": len(synthetic_paths),
        "epochs": int(max(1, int(epochs))),
        "lr": lr,
        "accuracy_before": round(before_acc, 6),
        "accuracy_after": round(after_acc, 6),
        "promoted": promoted,
    }
    _RETRAIN_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RETRAIN_METRICS_FILE.write_text(
        json.dumps(metrics_payload, indent=2), encoding="utf-8"
    )

    if promoted:
        updated_model.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "class_names": class_names,
                "retrained_from_synthetic": {
                    "timestamp": metrics_payload["timestamp"],
                    "target_class": target_class,
                    "synthetic_samples": len(synthetic_paths),
                    "accuracy_before": before_acc,
                    "accuracy_after": after_acc,
                },
            },
            str(updated_model),
        )

    return {
        "retrained": True,
        "promoted": promoted,
        "target_class": target_class,
        "synthetic_samples": len(synthetic_paths),
        "accuracy_before": round(before_acc, 6),
        "accuracy_after": round(after_acc, 6),
        "updated_model_path": str(updated_model),
        "metrics_path": str(_RETRAIN_METRICS_FILE),
    }
