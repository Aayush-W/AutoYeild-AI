"""
Thread-safe Grad-CAM for EfficientNet-B0.

Fixes applied vs the previous revision:
- register_full_backward_hook replaced with register_backward_hook for
  compatibility with all supported PyTorch versions AND because the full-backward
  hook's grad_output tuple refers to grads w.r.t. layer *inputs*, not *outputs*,
  which produced incorrect/misleading heatmaps.
- Per-call local closure variables still used (fixes the original global-state
  race condition without breaking correctness).
- threading.Lock still in place around forward+backward pass.
- Activations captured via detach().clone() to avoid retaining the graph.
- No in-place mutation of the captured activation tensor.
"""
from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

from src.inference.model_loader import get_default_model
from src.utils.preprocessing import get_inference_transform, IMAGE_SIZE
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "heatmaps"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Load model (Shared singleton)
# ---------------------------------------------------------------------------
model, class_names, meta = get_default_model()
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model.to(DEVICE)
model.eval()

# Target layer for Grad-CAM
# ConvNeXt class provides a helper property; EfficientNet is hardcoded
if meta["model_type"] == "convnext_small":
    _target_layer = model.target_layer
else:
    _target_layer = model.features[-1]

# Serialise forward+backward so concurrent async requests don't mix gradients
_gradcam_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Transform  (must match training normalisation exactly)
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
        # Per-call local lists — no global state
        _activations: list[torch.Tensor] = []
        _gradients: list[torch.Tensor] = []

        # register_backward_hook: hook(module, grad_input, grad_output)
        # grad_output[0] is the gradient of the loss w.r.t. the OUTPUT of this
        # layer — which is exactly what Grad-CAM needs.
        def _fwd_hook(module, input_, output):  # noqa: N802
            # Clone so we hold a snapshot even after the tensor is freed
            _activations.append(output.detach().clone())

        def _bwd_hook(module, grad_input, grad_output):  # noqa: N802
            # grad_output[0]: gradient of loss w.r.t. this layer's output tensor
            _gradients.append(grad_output[0].detach().clone())

        fwd_handle = _target_layer.register_forward_hook(_fwd_hook)
        # Use register_backward_hook (compatible with all supported PyTorch versions)
        bwd_handle = _target_layer.register_backward_hook(_bwd_hook)

        try:
            output = model(input_tensor)
            pred_class = output.argmax(dim=1).item()

            model.zero_grad()
            output[0, pred_class].backward()
        finally:
            # Always deregister — even if backward raises
            fwd_handle.remove()
            bwd_handle.remove()

        if not _activations or not _gradients:
            raise RuntimeError(
                "Grad-CAM hooks did not capture data. "
                "Check that _target_layer is in the forward path."
            )

        acts = _activations[0]   # (1, C, H, W)
        grads = _gradients[0]    # (1, C, H, W)

    # --- Pure tensor math — outside the lock ---
    pooled_grads = grads.mean(dim=[0, 2, 3])      # (C,)  global-average-pooled

    # Weight each channel; use a fresh clone — no in-place mutation of `acts`
    weighted_acts = acts.clone()
    for i in range(weighted_acts.shape[1]):
        weighted_acts[:, i, :, :] *= pooled_grads[i]

    heatmap = weighted_acts.mean(dim=1).squeeze()  # (H, W)
    heatmap = F.relu(heatmap)

    max_val = heatmap.max()
    if max_val > 0:
        heatmap = heatmap / max_val
    # If max_val == 0 (blank image / uniform prediction) heatmap stays all-zero

    heatmap_np = heatmap.cpu().numpy()
    heatmap_np = cv2.resize(heatmap_np, IMAGE_SIZE)
    heatmap_np = np.uint8(255 * heatmap_np)

    image_np = np.array(image.resize(IMAGE_SIZE))
    heatmap_color = cv2.applyColorMap(heatmap_np, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(image_np, 0.6, heatmap_color, 0.4, 0)

    output_path = OUTPUT_DIR / f"gradcam_{Path(image_path).name}"
    cv2.imwrite(str(output_path), overlay)

    return class_names[pred_class], str(output_path)
