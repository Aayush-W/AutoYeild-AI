"""
Evaluate the CNN (baseline or updated) on validation data.
Run from project root: python scripts/eval_cnn.py
Optional: python scripts/eval_cnn.py --model models/updated_model.pt
"""
import argparse
import json
import os
import sys

# Run from project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

import torch
import torch.nn as nn
from torchvision import datasets, transforms
from torchvision.models import efficientnet_b0
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score

from src.evaluation.metrics import compute_classification_metrics

DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32

def main():
    parser = argparse.ArgumentParser(description="Evaluate CNN on validation set")
    parser.add_argument("--model", default="models/baseline_model.pt", help="Path to .pt checkpoint")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Model not found: {args.model}")
        sys.exit(1)

    val_dir = os.path.join(DATA_DIR, "val")
    if not os.path.isdir(val_dir):
        print(f"Validation data not found: {val_dir}")
        sys.exit(1)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Using device:", device)

    val_transform = transforms.Compose([
        transforms.Resize(IMAGE_SIZE),
        transforms.ToTensor(),
    ])
    val_dataset = datasets.ImageFolder(root=val_dir, transform=val_transform)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    class_names = val_dataset.classes

    checkpoint = torch.load(args.model, map_location=device)
    class_names_ckpt = checkpoint["class_names"]
    num_classes = len(class_names_ckpt)
    if class_names_ckpt != list(class_names):
        print("Warning: checkpoint class_names differ from dataset folders. Using checkpoint names.")

    model = efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    model.eval()

    preds, targets = [], []
    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs, 1)
            preds.extend(predicted.cpu().numpy())
            targets.extend(labels.numpy())

    acc = accuracy_score(targets, preds)
    metrics = compute_classification_metrics(targets, preds, class_names)

    print("\n" + "=" * 50)
    print("CNN evaluation results")
    print("=" * 50)
    print(f"Model: {args.model}")
    print(f"Validation accuracy: {acc:.4f}")
    print(f"Macro precision:     {metrics['macro_precision']:.4f}")
    print(f"Macro recall:        {metrics['macro_recall']:.4f}")
    print(f"Macro F1:            {metrics['macro_f1']:.4f}")
    print("\nPer-class metrics:")
    for p in metrics["per_class"]:
        print(f"  {p['label']}: P={p['precision']:.3f} R={p['recall']:.3f} F1={p['f1']:.3f} (n={p['support']})")
    print("\nConfusion matrix (rows=true, cols=pred):")
    print(metrics["confusion_matrix"])
    print("=" * 50)

    out_dir = os.path.join(PROJECT_ROOT, "outputs", "metrics")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "eval_results.json")
    with open(out_path, "w") as f:
        json.dump({"accuracy": acc, **metrics}, f, indent=2)
    print(f"\nMetrics saved to {out_path}")

if __name__ == "__main__":
    main()
