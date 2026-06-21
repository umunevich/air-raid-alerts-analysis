"""Tests for exposure forecast prediction."""

from pathlib import Path

import pandas as pd
import pytest

from air_raid_alerts.models.exposure import fit_exposure_model
from air_raid_alerts.models.persist import load_exposure_model, save_exposure_model
from air_raid_alerts.models.predict import format_forecast, parse_origin_hour, predict_exposure_forecast
from air_raid_alerts.schema import FeatureCol, PanelCol, ProcessedCol, exposure_label
from helpers import utc


def _training_matrix() -> pd.DataFrame:
    rows = []
    for hour in range(8):
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
                ProcessedCol.SPLIT: "train",
                ProcessedCol.IN_PRIMARY_TRAIN: True,
            }
        )
    return pd.DataFrame(rows)


def test_save_and_load_exposure_model(tmp_path: Path) -> None:
    matrix = _training_matrix()
    model = fit_exposure_model(matrix, "kyiv_city", horizons=[1, 2])
    model_path = tmp_path / "model.joblib"
    save_exposure_model(model, model_path)
    loaded = load_exposure_model("kyiv_city", path=model_path)
    assert loaded.region_id == "kyiv_city"
    assert loaded.horizons == (1, 2)


def test_predict_exposure_forecast_latest_origin(tmp_path: Path) -> None:
    matrix = _training_matrix()
    matrix_path = tmp_path / "training_matrix.csv"
    matrix.to_csv(matrix_path, index=False)

    model = fit_exposure_model(matrix, "kyiv_city", horizons=[1, 2])
    model_path = tmp_path / "model.joblib"
    save_exposure_model(model, model_path)

    forecast = predict_exposure_forecast(
        "kyiv_city",
        at="latest",
        training_matrix_path=matrix_path,
        model_path=model_path,
    )
    assert forecast.region_id == "kyiv_city"
    assert forecast.probabilities[1] == pytest.approx(
        model.predict(matrix.iloc[[-1]])["pred_y_1"].iloc[0]
    )
    assert len(forecast.probabilities) == 2


def test_format_forecast_matches_requirements_shape() -> None:
    from air_raid_alerts.models.predict import ExposureForecast

    rendered = format_forecast(
        ExposureForecast(
            region_id="kyiv_city",
            region_name="Kyiv City",
            origin_hour_utc=utc(2024, 6, 1, 7),
            origin_hour_local=utc(2024, 6, 1, 7),
            probabilities={1: 0.12, 2: 0.18},
        )
    )
    assert "Horizon (hours)    P(under alert)" in rendered
    assert "1                  0.12" in rendered
    assert "2                  0.18" in rendered


def test_parse_origin_hour_accepts_iso_and_latest() -> None:
    matrix = _training_matrix()
    latest = parse_origin_hour("latest", matrix)
    assert latest == pd.Timestamp(utc(2024, 6, 1, 7))
    explicit = parse_origin_hour("2024-06-01T05:30:00Z", matrix)
    assert explicit == pd.Timestamp(utc(2024, 6, 1, 5))
