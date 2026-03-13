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
    heatmap_np = cv2.resize(heatmap_np, IMAGE_SIZE)
    heatmap_np = np.uint8(255 * heatmap_np)

    image_np = np.array(image.resize(IMAGE_SIZE))
    heatmap_color = cv2.applyColorMap(heatmap_np, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(image_np, 0.6, heatmap_color, 0.4, 0)

    output_path = OUTPUT_DIR / f"gradcam_{Path(image_path).name}"
    cv2.imwrite(str(output_path), overlay)

    return class_names[pred_class], str(output_path)
