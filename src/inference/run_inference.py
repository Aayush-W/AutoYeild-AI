import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
from src.inference.model_loader import get_default_model
from src.utils.preprocessing import get_inference_transform

# -------------------------
# Load model (Shared singleton)
# -------------------------
model, class_names, meta = get_default_model()
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model.to(DEVICE)
model.eval()

# -------------------------
# Transform (match training: Resize, CenterCrop, ImageNet norm)
# -------------------------
transform = get_inference_transform()

# -------------------------
# Inference
# -------------------------
def predict(image_path):
    image = Image.open(image_path).convert("RGB")
    image = transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        outputs = model(image)
        probs = torch.softmax(outputs, dim=1)
        conf, pred = torch.max(probs, 1)

    return class_names[pred.item()], conf.item()


def predict_with_probs(image_path, topk=3):
    image = Image.open(image_path).convert("RGB")
    image = transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        outputs = model(image)
        probs = torch.softmax(outputs, dim=1).squeeze(0)
        top_probs, top_indices = torch.topk(probs, k=min(topk, len(class_names)))

    results = []
    for prob, idx in zip(top_probs.tolist(), top_indices.tolist()):
        results.append({"label": class_names[idx], "prob": float(prob)})

    pred_idx = int(top_indices[0])
    return class_names[pred_idx], float(top_probs[0]), results

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_inference.py <image_path>")
        sys.exit(1)

    img_path = sys.argv[1]
    label, confidence = predict(img_path)

    print(f"Prediction: {label}")
    print(f"Confidence: {confidence:.4f}")
    
