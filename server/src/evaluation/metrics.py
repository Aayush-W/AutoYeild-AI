from typing import Dict, List, Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
)


def compute_classification_metrics(
    targets: List[int],
    preds: List[int],
    class_names: List[str],
) -> Dict[str, Any]:
    accuracy = float(accuracy_score(targets, preds))
    precision, recall, f1, _ = precision_recall_fscore_support(
        targets, preds, labels=list(range(len(class_names))), zero_division=0
    )
    conf = confusion_matrix(targets, preds, labels=list(range(len(class_names))))

    per_class = []
    for idx, name in enumerate(class_names):
        per_class.append(
            {
                "label": name,
                "precision": float(precision[idx]),
                "recall": float(recall[idx]),
                "f1": float(f1[idx]),
                "support": int(np.sum(np.array(targets) == idx)),
            }
        )

    return {
        "accuracy": accuracy,
        "macro_precision": float(np.mean(precision)),
        "macro_recall": float(np.mean(recall)),
        "macro_f1": float(np.mean(f1)),
        "per_class": per_class,
        "confusion_matrix": conf.tolist(),
    }
