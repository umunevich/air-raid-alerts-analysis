"""Exposure forecast baselines from REQUIREMENTS.md."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from air_raid_alerts.schema import (
    FeatureCol,
    ProcessedCol,
    SplitName,
    exposure_label,
    label_horizons,
)

BASELINE_MARGINAL = "marginal"
BASELINE_SEASONAL = "seasonal"
BASELINE_PERSISTENCE = "persistence"

BASELINE_NAMES: tuple[str, ...] = (
    BASELINE_MARGINAL,
    BASELINE_SEASONAL,
    BASELINE_PERSISTENCE,
)


def baseline_prediction_column(baseline: str, horizon_hours: int) -> str:
    return f"pred_{baseline}_{exposure_label(horizon_hours)}"


@dataclass(frozen=True)
class HorizonBaselineRates:
    marginal: float
    seasonal_by_hour_of_week: dict[int, float]
    persistence_when_active: float
    persistence_when_inactive: float


@dataclass(frozen=True)
class FittedBaselines:
    horizons: tuple[int, ...]
    rates_by_horizon: dict[int, HorizonBaselineRates]

    def predict_marginal(self, horizon: int, count: int) -> np.ndarray:
        rate = self.rates_by_horizon[horizon].marginal
        return np.full(count, rate, dtype=np.float64)

    def predict_seasonal(self, horizon: int, hour_of_week: pd.Series) -> np.ndarray:
        rates = self.rates_by_horizon[horizon]
        mapped = hour_of_week.map(rates.seasonal_by_hour_of_week)
        return mapped.fillna(rates.marginal).to_numpy(dtype=np.float64)

    def predict_persistence(self, horizon: int, active_at_origin: pd.Series) -> np.ndarray:
        rates = self.rates_by_horizon[horizon]
        active = active_at_origin.astype(bool).to_numpy()
        return np.where(active, rates.persistence_when_active, rates.persistence_when_inactive)


def _default_fit_mask(training_matrix: pd.DataFrame) -> pd.Series:
    if ProcessedCol.SPLIT in training_matrix.columns:
        return training_matrix[ProcessedCol.SPLIT] == SplitName.TRAIN
    return pd.Series(True, index=training_matrix.index)


def _fit_horizon_rates(fit_df: pd.DataFrame, horizon: int) -> HorizonBaselineRates:
    label = exposure_label(horizon)
    if label not in fit_df.columns:
        raise ValueError(f"Missing label column: {label}")

    labels = fit_df[label]
    marginal = float(labels.mean()) if not fit_df.empty else 0.0

    seasonal = (
        fit_df.groupby(FeatureCol.HOUR_OF_WEEK_KYIV, observed=True)[label]
        .mean()
        .astype(float)
        .to_dict()
    )

    active_mask = fit_df[FeatureCol.ACTIVE_AT_ORIGIN].astype(bool)
    if active_mask.any():
        persistence_active = float(labels.loc[active_mask].mean())
    else:
        persistence_active = marginal

    inactive_mask = ~active_mask
    if inactive_mask.any():
        persistence_inactive = float(labels.loc[inactive_mask].mean())
    else:
        persistence_inactive = marginal

    return HorizonBaselineRates(
        marginal=marginal,
        seasonal_by_hour_of_week=seasonal,
        persistence_when_active=persistence_active,
        persistence_when_inactive=persistence_inactive,
    )


def fit_baselines(
    training_matrix: pd.DataFrame,
    *,
    horizons: range | list[int] | None = None,
    fit_mask: pd.Series | None = None,
) -> FittedBaselines:
    """
    Fit marginal, seasonal, and persistence baselines on the training split.

    Uses all ``split == train`` rows by default (full pre-validation history).
    """
    if FeatureCol.HOUR_OF_WEEK_KYIV not in training_matrix.columns:
        raise ValueError(f"Missing feature column: {FeatureCol.HOUR_OF_WEEK_KYIV}")
    if FeatureCol.ACTIVE_AT_ORIGIN not in training_matrix.columns:
        raise ValueError(f"Missing feature column: {FeatureCol.ACTIVE_AT_ORIGIN}")

    horizon_list = list(horizons) if horizons is not None else label_horizons(training_matrix)
    mask = fit_mask if fit_mask is not None else _default_fit_mask(training_matrix)
    fit_df = training_matrix.loc[mask]
    if fit_df.empty:
        raise ValueError("No training rows available to fit baselines")

    rates = {horizon: _fit_horizon_rates(fit_df, horizon) for horizon in horizon_list}
    return FittedBaselines(horizons=tuple(horizon_list), rates_by_horizon=rates)


def predict_baselines(
    fitted: FittedBaselines,
    rows: pd.DataFrame,
    *,
    baselines: tuple[str, ...] | list[str] = BASELINE_NAMES,
) -> pd.DataFrame:
    """Return per-row baseline probabilities for each horizon."""
    unknown = set(baselines) - set(BASELINE_NAMES)
    if unknown:
        raise ValueError(f"Unknown baseline names: {sorted(unknown)}")

    predictions: dict[str, pd.Series] = {}
    count = len(rows)
    hour_of_week = rows[FeatureCol.HOUR_OF_WEEK_KYIV]
    active_at_origin = rows[FeatureCol.ACTIVE_AT_ORIGIN]

    for horizon in fitted.horizons:
        if BASELINE_MARGINAL in baselines:
            column = baseline_prediction_column(BASELINE_MARGINAL, horizon)
            predictions[column] = pd.Series(
                fitted.predict_marginal(horizon, count),
                index=rows.index,
            )
        if BASELINE_SEASONAL in baselines:
            column = baseline_prediction_column(BASELINE_SEASONAL, horizon)
            predictions[column] = pd.Series(
                fitted.predict_seasonal(horizon, hour_of_week),
                index=rows.index,
            )
        if BASELINE_PERSISTENCE in baselines:
            column = baseline_prediction_column(BASELINE_PERSISTENCE, horizon)
            predictions[column] = pd.Series(
                fitted.predict_persistence(horizon, active_at_origin),
                index=rows.index,
            )

    return pd.DataFrame(predictions, index=rows.index)
