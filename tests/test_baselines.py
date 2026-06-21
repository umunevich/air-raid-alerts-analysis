"""Tests for exposure forecast baselines."""

import pandas as pd
import pytest

from air_raid_alerts.models.baselines import (
    BASELINE_MARGINAL,
    BASELINE_PERSISTENCE,
    BASELINE_SEASONAL,
    baseline_prediction_column,
    fit_baselines,
    predict_baselines,
)
from air_raid_alerts.schema import FeatureCol, PanelCol, ProcessedCol, exposure_label
from helpers import utc


def _training_matrix() -> pd.DataFrame:
    return pd.DataFrame(
        {
            PanelCol.REGION_ID: ["kyiv_city"] * 4,
            PanelCol.ORIGIN_HOUR: [
                utc(2024, 6, 1, 8),
                utc(2024, 6, 1, 9),
                utc(2024, 6, 1, 10),
                utc(2024, 6, 1, 11),
            ],
            FeatureCol.HOUR_OF_WEEK_KYIV: [8, 8, 9, 9],
            FeatureCol.ACTIVE_AT_ORIGIN: [1, 0, 1, 0],
            exposure_label(1): [1, 0, 1, 0],
            exposure_label(2): [1, 1, 1, 0],
            ProcessedCol.SPLIT: ["train", "train", "train", "test"],
            ProcessedCol.IN_PRIMARY_TRAIN: [True] * 4,
        }
    )


def test_marginal_baseline_uses_train_split_only() -> None:
    matrix = _training_matrix()
    fitted = fit_baselines(matrix, horizons=[1])
    preds = predict_baselines(
        fitted,
        matrix.loc[matrix[ProcessedCol.SPLIT] == "test"],
        baselines=[BASELINE_MARGINAL],
    )

    assert preds.iloc[0][baseline_prediction_column(BASELINE_MARGINAL, 1)] == pytest.approx(2 / 3)


def test_seasonal_baseline_stratifies_by_hour_of_week() -> None:
    matrix = _training_matrix()
    fitted = fit_baselines(matrix, horizons=[1])
    test_row = matrix.loc[matrix[ProcessedCol.SPLIT] == "test"]
    preds = predict_baselines(fitted, test_row, baselines=[BASELINE_SEASONAL])

    assert preds.iloc[0][baseline_prediction_column(BASELINE_SEASONAL, 1)] == 1.0


def test_persistence_baseline_uses_active_at_origin() -> None:
    matrix = _training_matrix()
    fitted = fit_baselines(matrix, horizons=[1])

    active_row = matrix.iloc[[0]]
    inactive_row = matrix.iloc[[1]]
    active_preds = predict_baselines(fitted, active_row, baselines=[BASELINE_PERSISTENCE])
    inactive_preds = predict_baselines(fitted, inactive_row, baselines=[BASELINE_PERSISTENCE])

    assert active_preds.iloc[0][baseline_prediction_column(BASELINE_PERSISTENCE, 1)] == 1.0
    assert inactive_preds.iloc[0][baseline_prediction_column(BASELINE_PERSISTENCE, 1)] == 0.0


def test_predict_baselines_returns_all_horizons_and_baselines() -> None:
    matrix = _training_matrix()
    fitted = fit_baselines(matrix, horizons=[1, 2])
    preds = predict_baselines(fitted, matrix)

    expected_columns = {
        baseline_prediction_column(name, horizon)
        for name in (BASELINE_MARGINAL, BASELINE_SEASONAL, BASELINE_PERSISTENCE)
        for horizon in (1, 2)
    }
    assert set(preds.columns) == expected_columns
    assert len(preds) == len(matrix)


def test_seasonal_baseline_falls_back_to_marginal_for_unseen_hour() -> None:
    matrix = _training_matrix()
    fitted = fit_baselines(matrix, horizons=[1])
    unseen = matrix.iloc[[0]].copy()
    unseen[FeatureCol.HOUR_OF_WEEK_KYIV] = 99
    preds = predict_baselines(fitted, unseen, baselines=[BASELINE_SEASONAL])

    assert preds.iloc[0][baseline_prediction_column(BASELINE_SEASONAL, 1)] == pytest.approx(2 / 3)
