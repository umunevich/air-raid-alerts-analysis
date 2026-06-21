"""Tests for exposure model training and evaluation."""

import pandas as pd
import pytest

from air_raid_alerts.models.calibration import calibrate_exposure_model
from air_raid_alerts.models.exposure import fit_exposure_model, model_prediction_column, primary_train_mask
from air_raid_alerts.models.train import evaluate_exposure_model
from air_raid_alerts.schema import FeatureCol, PanelCol, ProcessedCol, exposure_label
from helpers import utc


def _training_matrix() -> pd.DataFrame:
    rows = []
    for hour in range(12):
        active = 1 if hour % 4 == 0 else 0
        label = 1 if active else 0
        if hour < 6:
            split = "train"
            in_primary = True
        elif hour < 9:
            split = "validation"
            in_primary = False
        else:
            split = "test"
            in_primary = False
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
                ProcessedCol.SPLIT: split,
                ProcessedCol.IN_PRIMARY_TRAIN: in_primary,
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
    model = calibrate_exposure_model(model, matrix)
    report = evaluate_exposure_model(model, matrix, calibration_method="isotonic")

    assert report.region_id == "kyiv_city"
    assert report.train_rows == int(primary_train_mask(matrix).sum())
    assert report.validation_rows == 3
    assert report.test_rows == 3
    assert report.calibrated is True
    assert len(report.horizons) == 2
    assert report.horizons[0].persistence_baseline.brier_score >= 0.0
    assert hasattr(report.horizons[0], "brier_uplift_vs_persistence")


def test_fit_exposure_model_requires_primary_train_rows() -> None:
    matrix = _training_matrix()
    matrix[ProcessedCol.IN_PRIMARY_TRAIN] = False
    with pytest.raises(ValueError, match="No training rows"):
        fit_exposure_model(matrix, "kyiv_city", horizons=[1])


def test_calibration_improves_or_preserves_probability_range() -> None:
    matrix = _training_matrix()
    model = fit_exposure_model(matrix, "kyiv_city", horizons=[1])
    calibrated = calibrate_exposure_model(model, matrix)
    val = matrix.loc[matrix[ProcessedCol.SPLIT] == "validation"]
    preds = calibrated.predict(val)
    assert preds.min().min() >= 0.0
    assert preds.max().max() <= 1.0
