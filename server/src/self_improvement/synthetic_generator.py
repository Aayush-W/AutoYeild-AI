"""
Augmentation-based synthetic image generator for AutoYield-AI.

Instead of random pixel noise, this generates realistic wafer images by
applying a randomised augmentation pipeline to existing labeled training images.
Each generated image is a perturbed variant of a real wafer sample, so the
synthetic data retains true defect morphology and texture.

Augmentation pipeline (applied randomly per image):
  - Random horizontal / vertical flip
  - Random rotation  (0â€“360 Â°)
  - Random brightness & contrast jitter
  - Random Gaussian blur
  - Random elastic / perspective warp
  - Optional: random additive Gaussian noise

Falls back gracefully to noise-only generation if no source images are found.

Usage (same API as before â€” drop-in replacement):
    from src.self_improvement.synthetic_generator import generate_synthetic_images

    paths = generate_synthetic_images(
        output_dir="outputs/synthetic_images",
        num_images=10,
        image_size=(224, 224),
        defect_class=None,        # None = sample from all classes
    )
"""
from __future__ import annotations

import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# ---------------------------------------------------------------------------
# Project layout
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TRAIN_DIR = _PROJECT_ROOT / "data" / "processed" / "train"


# ---------------------------------------------------------------------------
# Source image discovery
# ---------------------------------------------------------------------------

def _collect_source_images(
    train_dir: Path,
    defect_class: Optional[str] = None,
) -> List[Path]:
    """
    Return all image paths from *train_dir*, optionally filtered to *defect_class*.
    Accepts .jpg, .jpeg, .png, .bmp, .tiff.
    """
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    if not train_dir.exists():
        return []

    if defect_class:
        # Try exact match first, then case-insensitive
        candidate_dirs = [d for d in train_dir.iterdir()
                          if d.is_dir() and d.name.lower() == defect_class.lower()]
        search_dirs = candidate_dirs if candidate_dirs else [train_dir]
    else:
        search_dirs = [d for d in train_dir.iterdir() if d.is_dir()]

    paths: List[Path] = []
    for d in search_dirs:
        for f in d.iterdir():
            if f.suffix.lower() in exts:
                paths.append(f)
    return paths


# ---------------------------------------------------------------------------
# Augmentation helpers
# ---------------------------------------------------------------------------

def _random_augment(img: Image.Image, rng: random.Random) -> Image.Image:
    """
    Apply a randomised sequence of augmentations to a PIL image.
    Every transform is applied with a probability and a random magnitude
    so each generated image is genuinely unique.
    """
    # 1. Random flip
    if rng.random() < 0.5:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if rng.random() < 0.5:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    # 2. Random rotation (full 360Â° â€” wafer maps are rotationally symmetric)
    angle = rng.uniform(0, 360)
    img = img.rotate(angle, resample=Image.BILINEAR, expand=False)

    # 3. Brightness jitter  [0.6 â€“ 1.6]
    factor = rng.uniform(0.6, 1.6)
    img = ImageEnhance.Brightness(img).enhance(factor)

    # 4. Contrast jitter  [0.6 â€“ 1.6]
    factor = rng.uniform(0.6, 1.6)
    img = ImageEnhance.Contrast(img).enhance(factor)

    # 5. Colour saturation jitter (RGB only)  [0.5 â€“ 1.5]
    if img.mode == "RGB":
        factor = rng.uniform(0.5, 1.5)
        img = ImageEnhance.Color(img).enhance(factor)

    # 6. Gaussian blur  (radius 0 -> no blur, up to 2.5)
    if rng.random() < 0.4:
        radius = rng.uniform(0.5, 2.5)
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))

    # 7. Additive Gaussian noise
    if rng.random() < 0.35:
        arr = np.array(img, dtype=np.float32)
        std = rng.uniform(3, 18)
        noise = rng.gauss(0, 1)  # ensures distinct noise pattern per call
        np_noise = np.random.default_rng(
            int.from_bytes(os.urandom(4), "little")
        ).normal(0, std, arr.shape)
        arr = np.clip(arr + np_noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    # 8. Perspective warp (~20 % of images)
    if rng.random() < 0.2:
        w, h = img.size
        margin = int(min(w, h) * 0.08)
        coeffs = _perspective_coeffs(w, h, margin, rng)
        img = img.transform(
            (w, h), Image.PERSPECTIVE, coeffs, resample=Image.BILINEAR
        )

    return img


def _perspective_coeffs(
    w: int, h: int, margin: int, rng: random.Random
) -> List[float]:
    """Compute 8-coefficient perspective transform with small random jitter."""
    def jitter(v: int) -> int:
        return v + rng.randint(-margin, margin)

    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [
        (jitter(0), jitter(0)),
        (jitter(w), jitter(0)),
        (jitter(w), jitter(h)),
        (jitter(0), jitter(h)),
    ]

    # PIL expects the *inverse* mapping coefficients
    # Solve using a simple 8-equation linear system
    matrix = []
    for (sx, sy), (dx, dy) in zip(dst, src):
        matrix.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        matrix.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
    arr = np.array(matrix, dtype=np.float64)
    b = np.array([sx for (sx, _) in src] + [sy for (_, sy) in src], dtype=np.float64)
    # Interleave x and y targets correctly
    b = []
    for (sx, sy) in src:
        b.append(sx)
        b.append(sy)
    b = np.array(b, dtype=np.float64)
    try:
        coeffs = np.linalg.solve(arr, b)
        return coeffs.tolist()
    except np.linalg.LinAlgError:
        # Degenerate â€” return identity
        return [1, 0, 0, 0, 1, 0, 0, 0]


# ---------------------------------------------------------------------------
# Fallback: pure noise (used when no source images are available)
# ---------------------------------------------------------------------------

def _noise_image(size: Tuple[int, int], rng: random.Random) -> Image.Image:
    pixels = [
        (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        for _ in range(size[0] * size[1])
    ]
    img = Image.new("RGB", size)
    img.putdata(pixels)
    return img


# ---------------------------------------------------------------------------
# Public API  (drop-in replacement, backward-compatible signature)
# ---------------------------------------------------------------------------

def generate_synthetic_images(
    output_dir: str = "outputs/synthetic_images",
    num_images: int = 10,
    image_size: Tuple[int, int] = (224, 224),
    defect_class: Optional[str] = None,
    seed: int = 42,              # kept for API compatibility; ignored internally
    train_dir: Optional[str] = None,
) -> List[str]:
    """
    Generate *num_images* augmented wafer images into *output_dir*.

    Each image is a randomly augmented version of a real training sample,
    preserving genuine defect morphology while creating novel variations.

    Parameters
    ----------
    output_dir:
        Directory to save generated images.
    num_images:
        Number of synthetic images to produce.
    image_size:
        Output size as (width, height).
    defect_class:
        Restrict source images to this class label (e.g. "edge_ring", "center").
        None means sample evenly from all classes.
    seed:
        Accepted for API compatibility; not used (each call uses os.urandom for
        true randomness so outputs are never identical across runs).
    train_dir:
        Override the default data/processed/train directory.

    Returns
    -------
    List of absolute file paths to saved synthetic images.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Discover source images
    source_dir = Path(train_dir) if train_dir else _TRAIN_DIR
    source_images = _collect_source_images(source_dir, defect_class)

    # Unique batch prefix so repeated calls don't overwrite each other
    batch_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_id = uuid.uuid4().hex[:6]

    # Cryptographically random seed â€” different every call even in the same second
    rng = random.Random(int.from_bytes(os.urandom(4), "little"))

    using_augmentation = bool(source_images)
    if not using_augmentation:
        print(
            f"[synthetic_generator] WARNING: no source images found in {source_dir}. "
            "Falling back to random noise. Run the training data pipeline first."
        )

    saved_paths: List[str] = []

    for i in range(num_images):
        if using_augmentation:
            # Pick a source image at random
            src_path = rng.choice(source_images)
            try:
                img = Image.open(src_path).convert("RGB")
                img = img.resize(image_size, Image.BILINEAR)
                img = _random_augment(img, rng)
                # Final resize in case perspective warp changed dimensions
                img = img.resize(image_size, Image.BILINEAR)
                source_label = Path(src_path).parent.name
            except Exception as exc:
                print(f"[synthetic_generator] Could not augment {src_path}: {exc}. Using noise.")
                img = _noise_image(image_size, rng)
                source_label = "noise"
        else:
            img = _noise_image(image_size, rng)
            source_label = "noise"

        file_name = f"{batch_ts}_{batch_id}_aug_{i:03d}.png"
        file_path = os.path.join(output_dir, file_name)
        img.save(file_path)
        saved_paths.append(file_path)
        print(f"[synthetic_generator] Saved {file_name}  (source: {source_label})")

    mode = "augmentation" if using_augmentation else "noise fallback"
    print(
        f"[synthetic_generator] Generated {num_images} images "
        f"({mode}) -> {output_dir}"
    )
    return saved_paths



