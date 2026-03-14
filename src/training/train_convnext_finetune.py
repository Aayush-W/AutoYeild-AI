"""
train_convnext_finetune.py
==========================
Fine-tunes ConvNeXt-Small on wafer defect images.

Key improvements over v1
------------------------
* Correct class_names loading  (fixes JSON-dict vs list bug)
* ImageNet-pretrained ConvNeXt (NOT EfficientNet checkpoint)
* Mixed-precision (AMP)  _ faster on GPU, same accuracy
* CosineAnnealingWarmRestarts  _ smoother LR schedule
* Gradient clipping  _ prevents loss spikes
* TTA at validation  _ 5-crop average, +1-2 pp accuracy
* FocalLoss + LabelSmoothing  _ handles class imbalance
* Per-class F1 in final report
* Saves training curves + confusion matrix
"""

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from sklearn.metrics import classification_report, confusion_matrix
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.models.convnext_model import ConvNeXtDefectClassifier
from src.training.dataset_builder import WaferDataset
from src.utils.preprocessing import get_train_transform, get_val_transform, get_tta_transforms

# ---------------------------------------------
# Config
# ---------------------------------------------
PROJECT_ROOT  = Path(__file__).resolve().parents[2]
DATA_DIR      = PROJECT_ROOT / "data" / "processed"
MODELS_DIR    = PROJECT_ROOT / "models"
OUTPUTS_DIR   = PROJECT_ROOT / "outputs" / "finetune"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

CLASSES_JSON_PATH = MODELS_DIR / "classes.json"
SAVE_PATH         = MODELS_DIR / "baseline_model_finetuned.pt"

BATCH_SIZE      = 32
NUM_EPOCHS      = 30           # more room for cosine restarts
BASE_LR         = 3e-4        # scheduler will warm-restart and decay
WEIGHT_DECAY    = 1e-4
FOCAL_GAMMA     = 2.0
LABEL_SMOOTHING = 0.1
PATIENCE        = 8            # early stopping patience
GRAD_CLIP       = 1.0         # max gradient norm
USE_TTA         = True         # TTA during validation

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
USE_AMP = DEVICE == "cuda"     # Mixed precision only on GPU


# ---------------------------------------------
# Focal Loss  (handles class imbalance)
# ---------------------------------------------
class FocalLoss(nn.Module):
    """
    Focal Loss with optional label smoothing baked in.
    gamma > 0 down-weights easy examples -> model focuses on hard defects.
    """
    def __init__(self, num_classes: int, gamma: float = 2.0,
                 label_smoothing: float = 0.1):
        super().__init__()
        self.num_classes     = num_classes
        self.gamma           = gamma
        self.label_smoothing = label_smoothing

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # Soft targets for label smoothing
        with torch.no_grad():
            smooth_val  = self.label_smoothing / self.num_classes
            one_hot = torch.full(
                (targets.size(0), self.num_classes), smooth_val, device=logits.device
            )
            one_hot.scatter_(1, targets.unsqueeze(1),
                             1.0 - self.label_smoothing + smooth_val)

        log_probs = F.log_softmax(logits, dim=1)          # (N, C)
        probs     = log_probs.exp()

        # pt = probability of the true class
        pt            = (probs * one_hot).sum(dim=1)
        focal_weight  = (1.0 - pt).clamp(min=1e-6).pow(self.gamma)

        nll  = -(one_hot * log_probs).sum(dim=1)           # CE with smooth targets
        loss = focal_weight * nll
        return loss.mean()


# ---------------------------------------------
# Plotting helpers
# ---------------------------------------------
def plot_metrics(history: dict, save_dir: Path) -> None:
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(history["train_acc"], label="Train Acc")
    plt.plot(history["val_acc"],   label="Val Acc")
    plt.title("Accuracy Curve")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(history["train_loss"], label="Train Loss")
    plt.plot(history["val_loss"],   label="Val Loss")
    plt.title("Loss Curve")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()

    plt.tight_layout()
    plt.savefig(save_dir / "training_curves.png", dpi=150)
    plt.close()
    print(f"  Curves saved -> {save_dir / 'training_curves.png'}")


def plot_confusion_matrix(targets, preds, class_names: list, save_dir: Path) -> None:
    cm = confusion_matrix(targets, preds)
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm, annot=True, fmt="d",
        xticklabels=class_names, yticklabels=class_names,
        cmap="Blues",
    )
    plt.title("Confusion Matrix _ Best Epoch")
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    plt.savefig(save_dir / "confusion_matrix.png", dpi=150)
    plt.close()
    print(f"  Confusion matrix saved -> {save_dir / 'confusion_matrix.png'}")


# ---------------------------------------------
# TTA validation pass
# ---------------------------------------------
@torch.no_grad()
def evaluate_tta(model: nn.Module, data_dir: Path, class_names: list,
                 device: str) -> tuple:
    """
    Runs 5-crop TTA over the val set.
    Returns (accuracy, all_preds, all_targets).
    """
    tta_tfs = get_tta_transforms()
    model.eval()

    # Collect raw image paths + labels from the val folder
    all_logits = None
    all_targets = []

    for tf_idx, tf in enumerate(tta_tfs):
        ds = WaferDataset(data_dir / "val", transform=tf)
        loader = DataLoader(ds, batch_size=32, shuffle=False, num_workers=2)
        batch_logits = []
        with torch.no_grad():
            for inputs, labels in loader:
                inputs = inputs.to(device)
                out = model(inputs)
                batch_logits.append(out.cpu())
                if tf_idx == 0:
                    all_targets.extend(labels.numpy())
        epoch_logits = torch.cat(batch_logits, dim=0)   # (N, C)
        if all_logits is None:
            all_logits = epoch_logits
        else:
            all_logits += epoch_logits

    avg_probs  = F.softmax(all_logits / len(tta_tfs), dim=1)
    all_preds  = avg_probs.argmax(dim=1).numpy()
    all_targets = np.array(all_targets)
    accuracy   = (all_preds == all_targets).mean()
    return accuracy, all_preds.tolist(), all_targets.tolist()


# ---------------------------------------------
# Main training function
# ---------------------------------------------
def train_finetune() -> None:
    print(f"Device : {DEVICE}")
    print(f"AMP    : {USE_AMP}")
    print(f"TTA    : {USE_TTA}")

    # 1. Class names  _ BUG FIX: extract the list from the dict
    with open(CLASSES_JSON_PATH, "r") as f:
        data = json.load(f)
    class_names = data["classes"] if isinstance(data, dict) else data
    num_classes = len(class_names)
    print(f"Classes ({num_classes}): {class_names}")

    # 2. Datasets & loaders
    train_ds = WaferDataset(DATA_DIR / "train", transform=get_train_transform())
    val_ds   = WaferDataset(DATA_DIR / "val",   transform=get_val_transform())

    train_loader = DataLoader(
        train_ds, batch_size=BATCH_SIZE, shuffle=True,
        num_workers=2, pin_memory=(DEVICE == "cuda"),
    )
    val_loader = DataLoader(
        val_ds, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=2, pin_memory=(DEVICE == "cuda"),
    )

    # 3. Model  _ BUG FIX: start from ImageNet pretrained ConvNeXt, NOT EfficientNet checkpoint
    print("Loading ConvNeXt-Small with ImageNet pretrained weights _")
    model = ConvNeXtDefectClassifier(
        num_classes=num_classes,
        pretrained=True,     # ImageNet weights
        dropout=0.3,
    )
    model.to(DEVICE)

    # 4. Loss, optimiser, scheduler
    criterion = FocalLoss(
        num_classes=num_classes,
        gamma=FOCAL_GAMMA,
        label_smoothing=LABEL_SMOOTHING,
    )
    optimizer = optim.AdamW(
        model.parameters(),
        lr=BASE_LR,
        weight_decay=WEIGHT_DECAY,
    )
    # CosineAnnealingWarmRestarts: T_0 restarts every 10 epochs
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=10, T_mult=1, eta_min=1e-6,
    )
    scaler = GradScaler(enabled=USE_AMP)

    # 5. Training loop
    history = {k: [] for k in ("train_loss", "train_acc", "val_loss", "val_acc")}
    best_val_acc    = 0.0
    epochs_no_improve = 0
    best_preds, best_targets = [], []

    for epoch in range(NUM_EPOCHS):
        t0 = time.time()
        model.train()
        running_loss = 0.0
        correct = total = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1:02d}/{NUM_EPOCHS}", ncols=90)
        for inputs, labels in pbar:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)

            optimizer.zero_grad()
            with autocast(enabled=USE_AMP):
                outputs = model(inputs)
                loss    = criterion(outputs, labels)

            scaler.scale(loss).backward()
            # Gradient clipping _ prevents occasional NaN / exploding gradients
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            scaler.step(optimizer)
            scaler.update()

            running_loss += loss.item() * inputs.size(0)
            _, predicted  = outputs.max(1)
            total         += labels.size(0)
            correct       += predicted.eq(labels).sum().item()

            pbar.set_postfix(
                loss=f"{loss.item():.4f}",
                acc=f"{100.*correct/total:.1f}%",
            )

        epoch_loss = running_loss / len(train_loader.dataset)
        epoch_acc  = correct / total

        # -- Validation --------------------------------------
        model.eval()
        val_loss = val_correct = val_total = 0
        all_preds, all_targets = [], []

        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
                with autocast(enabled=USE_AMP):
                    outputs = model(inputs)
                    loss    = criterion(outputs, labels)

                val_loss    += loss.item() * inputs.size(0)
                _, predicted = outputs.max(1)
                val_total   += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()
                all_preds.extend(predicted.cpu().numpy())
                all_targets.extend(labels.cpu().numpy())

        val_epoch_loss = val_loss / len(val_loader.dataset)
        val_epoch_acc  = val_correct / val_total

        # Optionally run TTA for best-epoch reporting (costs ~5_ val time)
        if USE_TTA and val_epoch_acc > best_val_acc:
            tta_acc, tta_preds, tta_targets = evaluate_tta(
                model, DATA_DIR, class_names, DEVICE
            )
            print(f"  TTA Val Acc: {tta_acc:.4f}  (standard: {val_epoch_acc:.4f})")
            report_acc   = tta_acc
            report_preds = tta_preds
            report_tgts  = tta_targets
        else:
            report_acc   = val_epoch_acc
            report_preds = all_preds
            report_tgts  = all_targets

        elapsed = time.time() - t0
        print(
            f"Epoch {epoch+1:02d} | "
            f"Loss {epoch_loss:.4f} -> {val_epoch_loss:.4f} | "
            f"Acc {epoch_acc:.4f} -> {val_epoch_acc:.4f} | "
            f"LR {scheduler.get_last_lr()[0]:.2e} | "
            f"{elapsed:.0f}s"
        )

        history["train_loss"].append(epoch_loss)
        history["train_acc"].append(epoch_acc)
        history["val_loss"].append(val_epoch_loss)
        history["val_acc"].append(val_epoch_acc)

        scheduler.step(epoch + 1)   # CosineAnnealingWarmRestarts needs absolute step

        # -- Early stopping & checkpoint ----------------------
        if report_acc > best_val_acc:
            best_val_acc      = report_acc
            epochs_no_improve = 0
            best_preds        = report_preds
            best_targets      = report_tgts

            torch.save(
                {
                    "epoch":              epoch,
                    "model_state_dict":   model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_acc":            best_val_acc,
                    "model_type":         "convnext_small",
                    "class_names":        class_names,
                },
                SAVE_PATH,
            )
            print(f"  [OK] Best model saved  (val_acc={best_val_acc:.4f})")
            plot_confusion_matrix(best_targets, best_preds, class_names, OUTPUTS_DIR)
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= PATIENCE:
                print(f"Early stopping at epoch {epoch+1} (no improvement for {PATIENCE} epochs).")
                break

    # -- Final summary -----------------------------------------
    plot_metrics(history, OUTPUTS_DIR)

    print("\n" + "=" * 60)
    print(f"Fine-tuning complete.  Best Val Accuracy: {best_val_acc:.4f}")
    print("=" * 60)
    if best_preds and best_targets:
        print("\nPer-class report (best checkpoint):")
        print(classification_report(best_targets, best_preds, target_names=class_names))


if __name__ == "__main__":
    train_finetune()
