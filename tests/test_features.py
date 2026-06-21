"""Tests for hourly supervised feature matrix."""

import pandas as pd

from air_raid_alerts.features.build import (
    build_feature_matrix,
    build_training_matrix,
    feature_column_names,
    load_feature_config,
)
from air_raid_alerts.schema import FeatureCol, PanelCol, ProcessedCol, active_sum_column, exposure_label
from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.intervals import build_merged_intervals
from air_raid_alerts.transform.panel import build_exposure_labels, build_hourly_panel
from air_raid_alerts.transform.pipeline import build_region_dataset
from helpers import intervals_df, sample_vadimkin_path, utc


def test_load_feature_config_matches_defaults() -> None:
    config = load_feature_config()
    assert config.lag_hours == (1, 3, 6, 24, 48, 168)
    assert config.display_timezone == "Europe/Kyiv"


def test_feature_matrix_columns(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    intervals, origins, features, training_matrix, _manifest = build_region_dataset(
        events, "kyiv_city"
    )

    expected = [PanelCol.REGION_ID, PanelCol.ORIGIN_HOUR, *feature_column_names()]
    assert list(features.columns) == expected
    assert len(features) == len(origins)
    assert len(training_matrix) == len(origins)
    assert exposure_label(1) in training_matrix.columns
    assert ProcessedCol.SPLIT in training_matrix.columns


def test_active_at_origin_and_lags_on_fixture(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    panel = build_hourly_panel(merged, utc(2024, 6, 1, 7), utc(2024, 6, 1, 14))
    features = build_feature_matrix(panel, merged, lag_hours=[1, 3])

    row_9 = features.loc[features[PanelCol.ORIGIN_HOUR] == utc(2024, 6, 1, 9)].iloc[0]
    assert row_9[FeatureCol.ACTIVE_AT_ORIGIN] == 1
    assert row_9[active_sum_column(1)] == 1
    assert row_9[active_sum_column(3)] == 1

    row_10 = features.loc[features[PanelCol.ORIGIN_HOUR] == utc(2024, 6, 1, 10)].iloc[0]
    assert row_10[FeatureCol.ACTIVE_AT_ORIGIN] == 0
    assert row_10[active_sum_column(1)] == 1


def test_lag_sums_exclude_current_hour(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    panel = build_hourly_panel(merged, utc(2024, 6, 1, 7), utc(2024, 6, 1, 14))
    features = build_feature_matrix(panel, merged, lag_hours=[1, 3, 6])

    origin = utc(2024, 6, 1, 11)
    row = features.loc[features[PanelCol.ORIGIN_HOUR] == origin].iloc[0]
    for lookback in (1, 3, 6):
        expected = int(
            panel.loc[panel[PanelCol.ORIGIN_HOUR] < origin].tail(lookback)[PanelCol.ACTIVE].sum()
        )
        assert row[active_sum_column(lookback)] == expected


def test_time_since_last_events(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    panel = build_hourly_panel(merged, utc(2024, 6, 1, 7), utc(2024, 6, 1, 14))
    features = build_feature_matrix(panel, merged)

    row_9 = features.loc[features[PanelCol.ORIGIN_HOUR] == utc(2024, 6, 1, 9)].iloc[0]
    assert row_9[FeatureCol.TIME_SINCE_LAST_START_H] == 1.0
    assert pd.isna(row_9[FeatureCol.TIME_SINCE_LAST_END_H])

    row_12 = features.loc[features[PanelCol.ORIGIN_HOUR] == utc(2024, 6, 1, 12)].iloc[0]
    assert row_12[FeatureCol.TIME_SINCE_LAST_START_H] == 0.0
    assert row_12[FeatureCol.TIME_SINCE_LAST_END_H] == 2.0


def test_calendar_features_use_kyiv_timezone() -> None:
    intervals = intervals_df("kyiv_city", [])
    origins = pd.DataFrame(
        {
            PanelCol.REGION_ID: "kyiv_city",
            PanelCol.ORIGIN_HOUR: [utc(2024, 6, 1, 21)],  # 2024-06-02 00:00 Kyiv (EEST)
            PanelCol.ACTIVE: [0],
        }
    )
    features = build_feature_matrix(origins, intervals)
    row = features.iloc[0]
    assert row[FeatureCol.HOUR_KYIV] == 0
    assert row[FeatureCol.DAY_OF_WEEK_KYIV] == 6
    assert row[FeatureCol.HOUR_OF_WEEK_KYIV] == 6 * 24


def test_training_matrix_joins_labels() -> None:
    intervals = intervals_df("kyiv_city", [(utc(2024, 6, 1, 10), utc(2024, 6, 1, 11))])
    origins = build_hourly_panel(intervals, utc(2024, 6, 1, 9), utc(2024, 6, 1, 12))
    labels = build_exposure_labels(intervals, origins[PanelCol.ORIGIN_HOUR], horizons=[1])
    origins = origins.merge(labels, on=[PanelCol.REGION_ID, PanelCol.ORIGIN_HOUR])
    origins[ProcessedCol.SPLIT] = "train"
    origins[ProcessedCol.IN_PRIMARY_TRAIN] = True

    features = build_feature_matrix(origins, intervals, lag_hours=[1])
    matrix = build_training_matrix(features, origins)
    assert matrix.loc[0, exposure_label(1)] == origins.iloc[0][exposure_label(1)]
