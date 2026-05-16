import os
from typing import Tuple

from torchvision import transforms


# Central image + normalization config (shared by training and inference)
IMAGE_SIZE: Tuple[int, int] = (224, 224)
RESIZE_SIZE: int = 256

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

_IMAGENET_NORM = transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)


def get_train_transform() -> transforms.Compose:
    """
    Training-time preprocessing.
    Must stay in sync with get_inference_transform() to avoid train/infer drift.
    """
    return transforms.Compose(
        [
            transforms.Resize(RESIZE_SIZE),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.RandomRotation(3),
            transforms.ColorJitter(brightness=0.1, contrast=0.1),
            transforms.ToTensor(),
            _IMAGENET_NORM,
        ]
    )


def get_val_transform() -> transforms.Compose:
    """Validation-time preprocessing (no heavy augmentation)."""
    return transforms.Compose(
        [
            transforms.Resize(RESIZE_SIZE),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.ToTensor(),
            _IMAGENET_NORM,
        ]
    )


def get_inference_transform() -> transforms.Compose:
    """
    Inference-time preprocessing used by the API, CLI, and sanity checks.
    Currently identical to validation transform on purpose.
    """
    return get_val_transform()


def describe_tensor_stats(tensor) -> dict:
    """
    Return basic stats for logging/debugging.
    Expects a float tensor (C, H, W) or (N, C, H, W).
    """
    import torch

    if tensor is None:
        return {}

    if tensor.ndim == 3:
        t = tensor
    elif tensor.ndim == 4:
        t = tensor[0]
    else:
        t = tensor

    return {
        "shape": list(tensor.shape),
        "min": float(t.min().item()),
        "max": float(t.max().item()),
        "mean": float(t.mean().item()),
        "std": float(t.std().item()),
    }
