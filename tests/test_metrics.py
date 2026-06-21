"""Tests for probabilistic evaluation metrics."""

import numpy as np
import pytest

from air_raid_alerts.evaluation.metrics import binary_probabilistic_metrics


def test_binary_probabilistic_metrics_perfect_predictions() -> None:
    y_true = np.array([0, 1, 0, 1], dtype=np.int8)
    y_pred = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float64)
    metrics = binary_probabilistic_metrics(y_true, y_pred, horizon=1)

    assert metrics.horizon == 1
    assert metrics.n_samples == 4
    assert metrics.brier_score == 0.0
    assert metrics.log_loss == pytest.approx(0.0)
    assert metrics.pr_auc == 1.0
