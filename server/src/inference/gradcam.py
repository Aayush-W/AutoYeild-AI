"""
Thread-safe Grad-CAM for the active baseline runtime model.
"""
from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from src.inference.model_loader import get_default_model, get_gradcam_target_layer
from src.utils.preprocessing import IMAGE_SIZE, get_inference_transform

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "heatmaps"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Load model once at import time (shared read-only across threads)
# ---------------------------------------------------------------------------
model, class_names, model_meta = get_default_model()
_target_layer = get_gradcam_target_layer(model, model_meta["model_type"])

# Serialise forward+backward so concurrent async requests don't mix gradients
_gradcam_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Transform (must match training normalisation exactly)
# ---------------------------------------------------------------------------
_transform = get_inference_transform()


def summarize_gradcam_overlay(overlay_path: str) -> dict[str, float | int | str]:
    """
    Estimate coarse attention-map descriptors from the saved Grad-CAM overlay.

    The saved overlay blends the raw image with a JET heatmap. We approximate
    model attention by scoring pixels where the red channel dominates, then
    derive a dominant region, spread score, hotspot count, and max intensity.
    """
    overlay = cv2.imread(str(overlay_path))
    if overlay is None:
        return {
            "dominant_region": "unknown",
            "spread_score": 0.0,
            "num_hotspots": 0,
            "max_activation": 0.0,
        }

    rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]

    attention = np.clip(red - 0.5 * (green + blue), 0.0, 1.0)
    max_activation = float(attention.max()) if attention.size else 0.0

    threshold = max(0.28, max_activation * 0.55)
    mask = (attention >= threshold).astype(np.uint8)
    spread_score = float(mask.mean()) if mask.size else 0.0

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    hotspot_count = 0
    min_area = max(6, int(mask.size * 0.0015))
    for label_index in range(1, num_labels):
        area = int(stats[label_index, cv2.CC_STAT_AREA])
        if area >= min_area:
            hotspot_count += 1

    h, w = attention.shape
    yy, xx = np.ogrid[:h, :w]
    center_y = h / 2.0
    center_x = w / 2.0
    norm_y = (yy - center_y) / max(h / 2.0, 1.0)
    norm_x = (xx - center_x) / max(w / 2.0, 1.0)
    radius = np.sqrt(norm_x**2 + norm_y**2)

    region_masks = {
        "center zone": radius <= 0.35,
        "edge ring": radius >= 0.72,
        "upper region": (radius > 0.35) & (yy < center_y),
        "lower region": (radius > 0.35) & (yy >= center_y),
        "left region": (radius > 0.35) & (xx < center_x),
        "right region": (radius > 0.35) & (xx >= center_x),
    }

    region_scores = {}
    for region_name, region_mask in region_masks.items():
        region_attention = attention[region_mask]
        region_scores[region_name] = float(region_attention.mean()) if region_attention.size else 0.0

    dominant_region = max(region_scores, key=region_scores.get) if region_scores else "unknown"
    if max(region_scores.values(), default=0.0) < 0.02:
        dominant_region = "diffuse / weak signal"

    return {
        "dominant_region": dominant_region,
        "spread_score": round(spread_score, 3),
        "num_hotspots": hotspot_count,
        "max_activation": round(max_activation, 3),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_gradcam(image_path: str) -> tuple[str, str]:
    """
    Compute Grad-CAM overlay for the predicted class of *image_path*.

    Returns
    -------
    (predicted_class_name, heatmap_overlay_path)

    Thread-safe via _gradcam_lock.
    """
    import gc

    image = Image.open(image_path).convert("RGB")
    input_tensor = _transform(image).unsqueeze(0).to(DEVICE)

    with _gradcam_lock:
        _activations: list[torch.Tensor] = []
        _gradients: list[torch.Tensor] = []

        def _fwd_hook(module, input_, output):  # noqa: N802
            _activations.append(output.detach().clone())

        def _bwd_hook(module, grad_input, grad_output):  # noqa: N802
            _gradients.append(grad_output[0].detach().clone())

        fwd_handle = _target_layer.register_forward_hook(_fwd_hook)
        bwd_handle = _target_layer.register_backward_hook(_bwd_hook)

        try:
            output = model(input_tensor)
            pred_class = output.argmax(dim=1).item()

            model.zero_grad()
            output[0, pred_class].backward()
        finally:
            fwd_handle.remove()
            bwd_handle.remove()

        if not _activations or not _gradients:
            raise RuntimeError(
                "Grad-CAM hooks did not capture data. "
                "Check that the target layer is in the forward path."
            )

        acts = _activations[0]
        grads = _gradients[0]

    pooled_grads = grads.mean(dim=[0, 2, 3])

    weighted_acts = acts.clone()
    for i in range(weighted_acts.shape[1]):
        weighted_acts[:, i, :, :] *= pooled_grads[i]

    heatmap = weighted_acts.mean(dim=1).squeeze()
    heatmap = F.relu(heatmap)

    max_val = heatmap.max()
    if max_val > 0:
        heatmap = heatmap / max_val

    heatmap_np = heatmap.cpu().numpy()

    # --- Free all gradient/activation tensors immediately after use ---
    del acts, grads, pooled_grads, weighted_acts, heatmap
    del _activations[:], _gradients[:]
    del output, input_tensor
    model.zero_grad(set_to_none=True)
    gc.collect()
    # -----------------------------------------------------------------

    heatmap_np = cv2.resize(heatmap_np, IMAGE_SIZE)
    heatmap_np = np.uint8(255 * heatmap_np)

    image_np = np.array(image.resize(IMAGE_SIZE))
    heatmap_color = cv2.applyColorMap(heatmap_np, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(image_np, 0.6, heatmap_color, 0.4, 0)

    output_path = OUTPUT_DIR / f"gradcam_{Path(image_path).name}"
    cv2.imwrite(str(output_path), overlay)

    # Free image arrays
    del image_np, heatmap_np, heatmap_color, overlay
    gc.collect()

    return class_names[pred_class], str(output_path)


