"""Probabilistic forecast evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss


@dataclass(frozen=True)
class HorizonMetrics:
    horizon: int
    n_samples: int
    positive_rate: float
    brier_score: float
    log_loss: float
    pr_auc: float


def binary_probabilistic_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    horizon: int,
) -> HorizonMetrics:
    labels = np.asarray(y_true, dtype=np.int8)
    probs = np.clip(np.asarray(y_pred, dtype=np.float64), 0.0, 1.0)
    if labels.shape != probs.shape:
        raise ValueError("y_true and y_pred must have the same shape")

    return HorizonMetrics(
        horizon=horizon,
        n_samples=int(labels.size),
        positive_rate=float(labels.mean()) if labels.size else 0.0,
        brier_score=float(brier_score_loss(labels, probs)),
        log_loss=float(log_loss(labels, probs, labels=[0, 1])),
        pr_auc=float(average_precision_score(labels, probs)) if labels.any() and (~labels.astype(bool)).any() else float("nan"),
    )
