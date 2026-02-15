import torch
import torch.nn as nn
from torchvision import transforms
from torchvision.models import efficientnet_b0
from PIL import Image
import sys

MODEL_PATH = "models/baseline_model.pt"
IMAGE_SIZE = (224, 224)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# -------------------------
# Load model
# -------------------------
checkpoint = torch.load(MODEL_PATH, map_location=DEVICE)
class_names = checkpoint["class_names"]
num_classes = len(class_names)

model = efficientnet_b0(weights=None)
in_features = model.classifier[1].in_features
model.classifier[1] = nn.Linear(in_features, num_classes)

model.load_state_dict(checkpoint["model_state_dict"])
model = model.to(DEVICE)
model.eval()

# -------------------------
# Transform (match training: Resize, CenterCrop, ImageNet norm)
# -------------------------
imagenet_norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(IMAGE_SIZE),
    transforms.ToTensor(),
    imagenet_norm,
])

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
    
