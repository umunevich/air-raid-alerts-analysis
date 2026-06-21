"""Per-horizon logistic exposure models."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from air_raid_alerts.models.baselines import label_horizons
from air_raid_alerts.schema import PanelCol, ProcessedCol, exposure_label, is_exposure_label


def model_prediction_column(horizon_hours: int) -> str:
    return f"pred_{exposure_label(horizon_hours)}"


def feature_columns_from_matrix(training_matrix: pd.DataFrame) -> list[str]:
    excluded = {
        PanelCol.REGION_ID,
        PanelCol.ORIGIN_HOUR,
        ProcessedCol.SPLIT,
        ProcessedCol.IN_PRIMARY_TRAIN,
    }
    return [
        column
        for column in training_matrix.columns
        if column not in excluded and not is_exposure_label(column)
    ]


def primary_train_mask(training_matrix: pd.DataFrame) -> pd.Series:
    if ProcessedCol.IN_PRIMARY_TRAIN not in training_matrix.columns:
        raise ValueError(f"Missing column: {ProcessedCol.IN_PRIMARY_TRAIN}")
    return training_matrix[ProcessedCol.IN_PRIMARY_TRAIN].astype(bool)


def test_split_mask(training_matrix: pd.DataFrame) -> pd.Series:
    if ProcessedCol.SPLIT not in training_matrix.columns:
        raise ValueError(f"Missing column: {ProcessedCol.SPLIT}")
    return training_matrix[ProcessedCol.SPLIT] == "test"


def _make_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(max_iter=2000, class_weight="balanced"),
            ),
        ]
    )


@dataclass(frozen=True)
class FittedExposureModel:
    region_id: str
    horizons: tuple[int, ...]
    feature_columns: tuple[str, ...]
    pipelines: dict[int, Pipeline]

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        missing = set(self.feature_columns) - set(rows.columns)
        if missing:
            raise ValueError(f"Missing feature columns: {sorted(missing)}")

        features = rows.loc[:, list(self.feature_columns)]
        predictions: dict[str, pd.Series] = {}
        for horizon in self.horizons:
            pipeline = self.pipelines[horizon]
            probabilities = pipeline.predict_proba(features)[:, 1]
            column = model_prediction_column(horizon)
            predictions[column] = pd.Series(probabilities, index=rows.index)
        return pd.DataFrame(predictions, index=rows.index)


def fit_exposure_model(
    training_matrix: pd.DataFrame,
    region_id: str,
    *,
    horizons: range | list[int] | None = None,
    fit_mask: pd.Series | None = None,
) -> FittedExposureModel:
    """Fit one logistic regression per horizon on the provided training rows."""
    feature_columns = feature_columns_from_matrix(training_matrix)
    if not feature_columns:
        raise ValueError("No feature columns found in training matrix")

    horizon_list = list(horizons) if horizons is not None else label_horizons(training_matrix)
    mask = fit_mask if fit_mask is not None else primary_train_mask(training_matrix)
    fit_df = training_matrix.loc[mask]
    if fit_df.empty:
        raise ValueError("No training rows available to fit exposure model")

    features = fit_df.loc[:, feature_columns]
    pipelines: dict[int, Pipeline] = {}
    for horizon in horizon_list:
        label = exposure_label(horizon)
        if label not in fit_df.columns:
            raise ValueError(f"Missing label column: {label}")

        pipeline = _make_pipeline()
        pipeline.fit(features, fit_df[label])
        pipelines[horizon] = pipeline

    return FittedExposureModel(
        region_id=region_id,
        horizons=tuple(horizon_list),
        feature_columns=tuple(feature_columns),
        pipelines=pipelines,
    )
