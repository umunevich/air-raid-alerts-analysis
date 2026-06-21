"""Save and load fitted exposure models."""

from __future__ import annotations

from pathlib import Path

import joblib

from air_raid_alerts.models.exposure import FittedExposureModel
from air_raid_alerts.paths import region_processed_dir

MODEL_FILENAME = "exposure_model.joblib"


def model_output_path(region_id: str) -> Path:
    return region_processed_dir(region_id) / MODEL_FILENAME


def save_exposure_model(model: FittedExposureModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_exposure_model(
    region_id: str,
    *,
    path: Path | None = None,
) -> FittedExposureModel:
    model_path = path or model_output_path(region_id)
    if not model_path.is_file():
        raise FileNotFoundError(
            f"Model not found: {model_path}. Run `air-alerts train --region {region_id}` first."
        )
    model = joblib.load(model_path)
    if not isinstance(model, FittedExposureModel):
        raise TypeError(f"Expected FittedExposureModel at {model_path}, got {type(model).__name__}")
    return model
