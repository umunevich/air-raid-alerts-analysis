"""Probability calibration for fitted exposure models."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from air_raid_alerts.models.exposure import (
    FittedExposureModel,
    model_prediction_column,
    validation_split_mask,
)
from air_raid_alerts.schema import exposure_label

CalibrationMethod = Literal["isotonic", "sigmoid"]


class IdentityCalibrator:
    """Pass-through when validation labels are single-class."""

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        return np.clip(probabilities, 0.0, 1.0)


HorizonCalibrator = IsotonicRegression | Pipeline | IdentityCalibrator


def _fit_horizon_calibrator(
    raw_probabilities: np.ndarray,
    labels: np.ndarray,
    *,
    method: CalibrationMethod,
) -> HorizonCalibrator:
    labels = np.asarray(labels, dtype=np.int8)
    raw_probabilities = np.clip(np.asarray(raw_probabilities, dtype=np.float64), 0.0, 1.0)

    if len(np.unique(labels)) < 2:
        return IdentityCalibrator()

    if method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_probabilities, labels)
        return calibrator

    platt = Pipeline(
        steps=[
            ("classifier", LogisticRegression(max_iter=1000)),
        ]
    )
    platt.fit(raw_probabilities.reshape(-1, 1), labels)
    return platt


def apply_horizon_calibrator(
    calibrator: HorizonCalibrator,
    raw_probabilities: np.ndarray,
) -> np.ndarray:
    raw_probabilities = np.clip(np.asarray(raw_probabilities, dtype=np.float64), 0.0, 1.0)
    if isinstance(calibrator, IdentityCalibrator):
        return calibrator.predict(raw_probabilities)
    if isinstance(calibrator, IsotonicRegression):
        return calibrator.predict(raw_probabilities)
    return calibrator.predict_proba(raw_probabilities.reshape(-1, 1))[:, 1]


def calibrate_exposure_model(
    model: FittedExposureModel,
    training_matrix: pd.DataFrame,
    *,
    method: CalibrationMethod = "isotonic",
    cal_mask: pd.Series | None = None,
) -> FittedExposureModel:
    """Fit per-horizon calibrators on validation rows; test is never used."""
    mask = cal_mask if cal_mask is not None else validation_split_mask(training_matrix)
    cal_df = training_matrix.loc[mask]
    if cal_df.empty:
        raise ValueError("No validation rows available for calibration")

    raw_preds = model.predict_raw(cal_df)
    calibrators: dict[int, HorizonCalibrator] = {}
    for horizon in model.horizons:
        label = exposure_label(horizon)
        calibrators[horizon] = _fit_horizon_calibrator(
            raw_preds[model_prediction_column(horizon)].to_numpy(),
            cal_df[label].to_numpy(),
            method=method,
        )

    return model.with_calibrators(calibrators)
