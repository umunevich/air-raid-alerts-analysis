"""Tests for exposure model training and evaluation."""

import pandas as pd
import pytest

from air_raid_alerts.models.exposure import (
    fit_exposure_model,
    model_prediction_column,
    primary_train_mask,
)
from air_raid_alerts.models.train import evaluate_exposure_model
from air_raid_alerts.schema import FeatureCol, PanelCol, ProcessedCol, exposure_label
from helpers import utc


def _training_matrix() -> pd.DataFrame:
    rows = []
    for hour in range(12):
        active = 1 if hour % 4 == 0 else 0
        label = 1 if active else 0
        rows.append(
            {
                PanelCol.REGION_ID: "kyiv_city",
                PanelCol.ORIGIN_HOUR: utc(2024, 6, 1, hour),
                FeatureCol.ACTIVE_AT_ORIGIN: active,
                FeatureCol.HOUR_OF_WEEK_KYIV: hour,
                FeatureCol.HOUR_KYIV: hour,
                FeatureCol.DAY_OF_WEEK_KYIV: 5,
                "active_sum_1h": active,
                exposure_label(1): label,
                exposure_label(2): label,
                ProcessedCol.SPLIT: "train" if hour < 8 else "test",
                ProcessedCol.IN_PRIMARY_TRAIN: hour < 8,
            }
        )
    return pd.DataFrame(rows)


def test_fit_exposure_model_uses_primary_train_mask() -> None:
    matrix = _training_matrix()
    model = fit_exposure_model(matrix, "kyiv_city", horizons=[1])
    preds = model.predict(matrix.loc[matrix[ProcessedCol.SPLIT] == "test"])
    assert preds[model_prediction_column(1)].between(0, 1).all()


def test_train_and_evaluate_reports_test_metrics() -> None:
    matrix = _training_matrix()
    model = fit_exposure_model(matrix, "kyiv_city", horizons=[1, 2])
    report = evaluate_exposure_model(model, matrix)

    assert report.region_id == "kyiv_city"
    assert report.train_rows == int(primary_train_mask(matrix).sum())
    assert report.test_rows == 4
    assert len(report.horizons) == 2
    assert report.horizons[0].model.brier_score >= 0.0


def test_fit_exposure_model_requires_primary_train_rows() -> None:
    matrix = _training_matrix()
    matrix[ProcessedCol.IN_PRIMARY_TRAIN] = False
    with pytest.raises(ValueError, match="No training rows"):
        fit_exposure_model(matrix, "kyiv_city", horizons=[1])
