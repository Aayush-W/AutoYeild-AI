import os
from typing import Tuple, List

import torch
from torchvision import transforms


# Central image + normalization config (shared by training and inference)
IMAGE_SIZE: Tuple[int, int] = (224, 224)
RESIZE_SIZE: int = 256

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

_IMAGENET_NORM = transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)


def get_train_transform() -> transforms.Compose:
    """
    Training-time preprocessing — aggressively augmented for wafer defect diversity.
    Augmentations chosen to simulate real manufacturing variance:
      - Spatial:   flip, rotate, random crop (handles partial defects)
      - Photometric: ColorJitter, GaussianBlur (sensor noise)
      - Occlusion: RandomErasing (particle contamination / scan artifacts)
    """
    return transforms.Compose(
        [
            transforms.Resize(RESIZE_SIZE),
            # Random rather than center crop — sees more of the wafer surface
            transforms.RandomCrop(IMAGE_SIZE),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.5),
            transforms.RandomRotation(degrees=15),
            transforms.ColorJitter(
                brightness=0.3,
                contrast=0.3,
                saturation=0.2,
                hue=0.05,
            ),
            # Simulates optical-scan blur / low-res sensors
            transforms.RandomApply(
                [transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5))],
                p=0.3,
            ),
            transforms.ToTensor(),
            _IMAGENET_NORM,
            # Simulates particle contamination / occlusion on wafer surface
            transforms.RandomErasing(
                p=0.3,
                scale=(0.02, 0.15),
                ratio=(0.3, 3.3),
                value="random",
            ),
        ]
    )


def get_val_transform() -> transforms.Compose:
    """Validation-time preprocessing — deterministic, no augmentation."""
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
    Identical to validation transform — no augmentation at single-image inference.
    """
    return get_val_transform()


def get_tta_transforms() -> List[transforms.Compose]:
    """
    Test-Time Augmentation: returns 5 deterministic transforms (original +
    4 flips/rotations).  Average their softmax outputs for +1-2% accuracy.
    """
    base = [transforms.Resize(RESIZE_SIZE), transforms.CenterCrop(IMAGE_SIZE)]
    augments = [
        [],                                              # Original
        [transforms.RandomHorizontalFlip(p=1.0)],       # H-flip
        [transforms.RandomVerticalFlip(p=1.0)],         # V-flip
        [transforms.RandomRotation(degrees=(90, 90))],  # 90° CW
        [transforms.RandomRotation(degrees=(270, 270))],# 270° CW
    ]
    transforms_list = []
    for aug in augments:
        transforms_list.append(
            transforms.Compose(base + aug + [transforms.ToTensor(), _IMAGENET_NORM])
        )
    return transforms_list


def describe_tensor_stats(tensor) -> dict:
    """
    Return basic stats for logging/debugging.
    Expects a float tensor (C, H, W) or (N, C, H, W).
    """
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
        "min":   float(t.min().item()),
        "max":   float(t.max().item()),
        "mean":  float(t.mean().item()),
        "std":   float(t.std().item()),
    }

