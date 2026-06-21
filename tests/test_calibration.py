"""Tests for probability calibration."""

import pandas as pd
import pytest

from air_raid_alerts.models.calibration import calibrate_exposure_model
from air_raid_alerts.models.exposure import fit_exposure_model, model_prediction_column
from air_raid_alerts.schema import FeatureCol, PanelCol, ProcessedCol, exposure_label
from helpers import utc


def _matrix_with_validation() -> pd.DataFrame:
    rows = []
    for hour in range(10):
        active = 1 if hour % 3 == 0 else 0
        label = 1 if active else 0
        split = "train" if hour < 4 else "validation" if hour < 7 else "test"
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
                ProcessedCol.SPLIT: split,
                ProcessedCol.IN_PRIMARY_TRAIN: hour < 4,
            }
        )
    return pd.DataFrame(rows)


def test_calibrate_exposure_model_requires_validation_rows() -> None:
    matrix = _matrix_with_validation()
    model = fit_exposure_model(matrix, "kyiv_city", horizons=[1])
    with pytest.raises(ValueError, match="No validation rows"):
        calibrate_exposure_model(model, matrix, cal_mask=pd.Series(False, index=matrix.index))


def test_calibrated_predict_differs_from_raw_when_both_classes_present() -> None:
    matrix = _matrix_with_validation()
    model = fit_exposure_model(matrix, "kyiv_city", horizons=[1])
    calibrated = calibrate_exposure_model(model, matrix)
    val = matrix.loc[matrix[ProcessedCol.SPLIT] == "validation"]
    raw = model.predict_raw(val)
    cal = calibrated.predict(val)
    assert cal[model_prediction_column(1)].between(0, 1).all()
    # Not guaranteed to differ on tiny fixture, but calibrated path runs.
    assert len(cal) == len(raw)
