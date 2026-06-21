"""Build hourly feature matrix for supervised exposure training."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from air_raid_alerts.paths import project_root
from air_raid_alerts.schema import (
    FeatureCol,
    PanelCol,
    ProcessedCol,
    active_sum_column,
    is_exposure_label,
)
from air_raid_alerts.time_intervals import (
    hours_since_last_event,
    interval_bounds_ns,
    or_intervals_cover_instants,
    timestamps_to_ns,
)

DEFAULT_LAG_HOURS: tuple[int, ...] = (1, 3, 6, 24, 48, 168)
DEFAULT_DISPLAY_TIMEZONE = "Europe/Kyiv"
FEATURES_CONFIG_PATH = project_root() / "configs" / "features.yaml"


@dataclass(frozen=True)
class FeatureConfig:
    lag_hours: tuple[int, ...]
    display_timezone: str


def load_feature_config(path: Path | None = None) -> FeatureConfig:
    config_path = path or FEATURES_CONFIG_PATH
    if not config_path.is_file():
        return FeatureConfig(
            lag_hours=DEFAULT_LAG_HOURS,
            display_timezone=DEFAULT_DISPLAY_TIMEZONE,
        )

    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    lag_hours = tuple(int(h) for h in raw.get("lags_hours", DEFAULT_LAG_HOURS))
    display_timezone = str(raw.get("display_timezone", DEFAULT_DISPLAY_TIMEZONE))
    return FeatureConfig(lag_hours=lag_hours, display_timezone=display_timezone)


def feature_column_names(lag_hours: tuple[int, ...] | list[int] | None = None) -> list[str]:
    lags = tuple(lag_hours) if lag_hours is not None else DEFAULT_LAG_HOURS
    return [
        FeatureCol.ACTIVE_AT_ORIGIN,
        *[active_sum_column(h) for h in lags],
        FeatureCol.TIME_SINCE_LAST_START_H,
        FeatureCol.TIME_SINCE_LAST_END_H,
        FeatureCol.HOUR_KYIV,
        FeatureCol.DAY_OF_WEEK_KYIV,
        FeatureCol.HOUR_OF_WEEK_KYIV,
    ]


def _active_at_instant_vectorized(
    intervals: pd.DataFrame,
    origin_ns: np.ndarray,
) -> np.ndarray:
    if intervals.empty:
        return np.zeros(len(origin_ns), dtype=np.int8)

    active = np.zeros(len(origin_ns), dtype=np.int8)
    starts, ends = interval_bounds_ns(intervals)
    or_intervals_cover_instants(starts, ends, origin_ns, active)
    return active


def _calendar_features(origin_hours: pd.Series, timezone: str) -> pd.DataFrame:
    local = pd.DatetimeIndex(origin_hours, tz="UTC").tz_convert(timezone)
    hour_kyiv = local.hour.astype(np.int16)
    dow_kyiv = local.dayofweek.astype(np.int16)
    return pd.DataFrame(
        {
            FeatureCol.HOUR_KYIV: hour_kyiv,
            FeatureCol.DAY_OF_WEEK_KYIV: dow_kyiv,
            FeatureCol.HOUR_OF_WEEK_KYIV: (dow_kyiv * 24 + hour_kyiv).astype(np.int16),
        }
    )


def _lag_sums(origins: pd.DataFrame, lag_hours: tuple[int, ...]) -> pd.DataFrame:
    ordered = origins.sort_values(PanelCol.ORIGIN_HOUR).reset_index(drop=True)
    past_active = ordered[PanelCol.ACTIVE].shift(1)
    lag_data: dict[str, pd.Series] = {}
    for lookback in lag_hours:
        if lookback < 1:
            raise ValueError("lag lookback must be >= 1")
        lag_data[active_sum_column(lookback)] = (
            past_active.rolling(lookback, min_periods=1).sum().fillna(0).astype(np.int16)
        )
    return pd.DataFrame(lag_data)


def build_feature_matrix(
    origins: pd.DataFrame,
    intervals: pd.DataFrame,
    *,
    lag_hours: tuple[int, ...] | list[int] | None = None,
    display_timezone: str = DEFAULT_DISPLAY_TIMEZONE,
) -> pd.DataFrame:
    """
    One row per forecast origin hour with features available at or before origin t.

    Lag sums use hourly ``active`` flags for hours strictly before ``origin_hour``.
    ``active_at_origin`` is alert state at instant t (persistence signal).
    """
    if origins.empty:
        return pd.DataFrame(
            columns=[PanelCol.REGION_ID, PanelCol.ORIGIN_HOUR, *feature_column_names(lag_hours)]
        )

    lags = tuple(lag_hours) if lag_hours is not None else DEFAULT_LAG_HOURS
    ordered = origins.sort_values(PanelCol.ORIGIN_HOUR).reset_index(drop=True)
    origin_ns = timestamps_to_ns(ordered[PanelCol.ORIGIN_HOUR])

    features = pd.DataFrame(
        {
            PanelCol.REGION_ID: ordered[PanelCol.REGION_ID],
            PanelCol.ORIGIN_HOUR: ordered[PanelCol.ORIGIN_HOUR],
            FeatureCol.ACTIVE_AT_ORIGIN: _active_at_instant_vectorized(intervals, origin_ns),
        }
    )
    features = pd.concat([features, _lag_sums(ordered, lags)], axis=1)

    if intervals.empty:
        features[FeatureCol.TIME_SINCE_LAST_START_H] = np.nan
        features[FeatureCol.TIME_SINCE_LAST_END_H] = np.nan
    else:
        starts, ends = interval_bounds_ns(intervals)
        features[FeatureCol.TIME_SINCE_LAST_START_H] = hours_since_last_event(origin_ns, starts)
        features[FeatureCol.TIME_SINCE_LAST_END_H] = hours_since_last_event(origin_ns, ends)

    calendar = _calendar_features(ordered[PanelCol.ORIGIN_HOUR], display_timezone)
    features = pd.concat([features, calendar], axis=1)
    return features


def build_training_matrix(
    features: pd.DataFrame,
    origins: pd.DataFrame,
) -> pd.DataFrame:
    """Join feature rows with exposure labels and split metadata for modeling."""
    label_columns = [c for c in origins.columns if is_exposure_label(c)]
    meta_columns = [ProcessedCol.SPLIT, ProcessedCol.IN_PRIMARY_TRAIN]
    origin_columns = [PanelCol.REGION_ID, PanelCol.ORIGIN_HOUR]
    labels = origins[origin_columns + label_columns + meta_columns]
    return features.merge(labels, on=origin_columns, how="inner", validate="one_to_one")
