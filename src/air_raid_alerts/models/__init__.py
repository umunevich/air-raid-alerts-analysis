"""Forecast models and calibration."""

from air_raid_alerts.models.baselines import (
    BASELINE_MARGINAL,
    BASELINE_NAMES,
    BASELINE_PERSISTENCE,
    BASELINE_SEASONAL,
    FittedBaselines,
    baseline_prediction_column,
    fit_baselines,
    predict_baselines,
)
from air_raid_alerts.schema import label_horizons
from air_raid_alerts.models.calibration import CalibrationMethod, calibrate_exposure_model
from air_raid_alerts.models.exposure import (
    FittedExposureModel,
    feature_columns_from_matrix,
    fit_exposure_model,
    model_prediction_column,
    primary_train_mask,
    test_split_mask,
    validation_split_mask,
)
from air_raid_alerts.models.persist import (
    load_exposure_model,
    model_output_path,
    save_exposure_model,
)
from air_raid_alerts.models.predict import (
    ExposureForecast,
    format_forecast,
    predict_exposure_forecast,
)
from air_raid_alerts.models.train import (
    ExposureTrainingReport,
    HorizonEvaluation,
    format_report,
    load_training_matrix,
    metrics_output_path,
    train_and_evaluate,
    write_report_json,
)

__all__ = [
    "BASELINE_MARGINAL",
    "BASELINE_NAMES",
    "BASELINE_PERSISTENCE",
    "BASELINE_SEASONAL",
    "CalibrationMethod",
    "ExposureForecast",
    "ExposureTrainingReport",
    "FittedBaselines",
    "FittedExposureModel",
    "HorizonEvaluation",
    "baseline_prediction_column",
    "calibrate_exposure_model",
    "feature_columns_from_matrix",
    "fit_baselines",
    "fit_exposure_model",
    "format_forecast",
    "format_report",
    "label_horizons",
    "load_exposure_model",
    "load_training_matrix",
    "metrics_output_path",
    "model_output_path",
    "model_prediction_column",
    "predict_baselines",
    "predict_exposure_forecast",
    "primary_train_mask",
    "save_exposure_model",
    "test_split_mask",
    "train_and_evaluate",
    "validation_split_mask",
    "write_report_json",
]
