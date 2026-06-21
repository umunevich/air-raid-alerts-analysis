"""Train exposure models and evaluate on held-out test data."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from air_raid_alerts.evaluation.metrics import HorizonMetrics, binary_probabilistic_metrics
from air_raid_alerts.models.baselines import (
    BASELINE_SEASONAL,
    baseline_prediction_column,
    fit_baselines,
    predict_baselines,
)
from air_raid_alerts.models.exposure import (
    FittedExposureModel,
    fit_exposure_model,
    model_prediction_column,
    primary_train_mask,
    test_split_mask,
)
from air_raid_alerts.models.persist import model_output_path, save_exposure_model
from air_raid_alerts.paths import region_processed_dir
from air_raid_alerts.regions import get_region
from air_raid_alerts.schema import exposure_label
from air_raid_alerts.transform.pipeline import TRAINING_MATRIX_FILENAME

METRICS_FILENAME = "exposure_model_metrics.json"


@dataclass(frozen=True)
class HorizonEvaluation:
    horizon: int
    model: HorizonMetrics
    seasonal_baseline: HorizonMetrics
    brier_uplift_vs_seasonal: float


@dataclass(frozen=True)
class ExposureTrainingReport:
    region_id: str
    train_rows: int
    test_rows: int
    feature_count: int
    horizons: tuple[HorizonEvaluation, ...]


def training_matrix_path(region_id: str) -> Path:
    return region_processed_dir(region_id) / TRAINING_MATRIX_FILENAME


def load_training_matrix(
    region_id: str,
    *,
    csv_path: Path | None = None,
) -> pd.DataFrame:
    get_region(region_id)
    path = csv_path or training_matrix_path(region_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"Training matrix not found: {path}. Run `air-alerts process --region {region_id}` first."
        )
    return pd.read_csv(path, parse_dates=["origin_hour"])


def evaluate_exposure_model(
    model: FittedExposureModel,
    training_matrix: pd.DataFrame,
    *,
    eval_mask: pd.Series | None = None,
) -> ExposureTrainingReport:
    mask = eval_mask if eval_mask is not None else test_split_mask(training_matrix)
    eval_df = training_matrix.loc[mask]
    if eval_df.empty:
        raise ValueError("No evaluation rows available")

    seasonal_baseline = fit_baselines(training_matrix)
    model_preds = model.predict(eval_df)
    seasonal_preds = predict_baselines(seasonal_baseline, eval_df, baselines=[BASELINE_SEASONAL])

    horizon_evaluations: list[HorizonEvaluation] = []
    for horizon in model.horizons:
        label = exposure_label(horizon)
        y_true = eval_df[label].to_numpy(dtype=np.int8)
        model_metrics = binary_probabilistic_metrics(
            y_true,
            model_preds[model_prediction_column(horizon)].to_numpy(),
            horizon=horizon,
        )
        seasonal_column = baseline_prediction_column(BASELINE_SEASONAL, horizon)
        seasonal_metrics = binary_probabilistic_metrics(
            y_true,
            seasonal_preds[seasonal_column].to_numpy(),
            horizon=horizon,
        )
        horizon_evaluations.append(
            HorizonEvaluation(
                horizon=horizon,
                model=model_metrics,
                seasonal_baseline=seasonal_metrics,
                brier_uplift_vs_seasonal=seasonal_metrics.brier_score - model_metrics.brier_score,
            )
        )

    train_mask = primary_train_mask(training_matrix)
    return ExposureTrainingReport(
        region_id=model.region_id,
        train_rows=int(train_mask.sum()),
        test_rows=int(mask.sum()),
        feature_count=len(model.feature_columns),
        horizons=tuple(horizon_evaluations),
    )


def train_and_evaluate(
    region_id: str,
    *,
    csv_path: Path | None = None,
    save_model: bool = True,
) -> tuple[FittedExposureModel, ExposureTrainingReport]:
    """Fit per-horizon logistic models on primary train rows and score the test split."""
    training_matrix = load_training_matrix(region_id, csv_path=csv_path)
    model = fit_exposure_model(
        training_matrix,
        region_id,
        fit_mask=primary_train_mask(training_matrix),
    )
    if save_model:
        save_exposure_model(model, model_output_path(region_id))
    report = evaluate_exposure_model(model, training_matrix)
    return model, report


def format_report(report: ExposureTrainingReport) -> str:
    lines = [
        f"Region: {report.region_id}",
        f"Primary train rows: {report.train_rows:,}",
        f"Test rows: {report.test_rows:,}",
        f"Features: {report.feature_count}",
        "",
        "Horizon  Pos%   Brier   LogLoss  PR-AUC   Seasonal Brier  Brier uplift",
    ]
    for item in report.horizons:
        model = item.model
        seasonal = item.seasonal_baseline
        pr_auc = f"{model.pr_auc:6.3f}" if not np.isnan(model.pr_auc) else "   n/a"
        lines.append(
            f"{model.horizon:7d}  {model.positive_rate:5.1%}  {model.brier_score:6.4f}  "
            f"{model.log_loss:6.4f}  {pr_auc}  {seasonal.brier_score:13.4f}  "
            f"{item.brier_uplift_vs_seasonal:12.4f}"
        )
    return "\n".join(lines)


def write_report_json(report: ExposureTrainingReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "region_id": report.region_id,
        "train_rows": report.train_rows,
        "test_rows": report.test_rows,
        "feature_count": report.feature_count,
        "horizons": [
            {
                "horizon": item.horizon,
                "model": asdict(item.model),
                "seasonal_baseline": asdict(item.seasonal_baseline),
                "brier_uplift_vs_seasonal": item.brier_uplift_vs_seasonal,
            }
            for item in report.horizons
        ],
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def metrics_output_path(region_id: str) -> Path:
    return region_processed_dir(region_id) / METRICS_FILENAME
