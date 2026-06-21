"""Tests for hourly panel and exposure labels."""

import pandas as pd

from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.intervals import build_merged_intervals
from air_raid_alerts.transform.panel import (
    build_exposure_labels,
    build_hourly_panel,
    exposure_in_forward_window,
    is_active_in_hour,
)
from air_raid_alerts.schema import PanelCol, exposure_label, is_exposure_label
from helpers import intervals_df, sample_vadimkin_path, utc


def test_is_active_in_hour_half_open_convention() -> None:
    intervals = intervals_df("kyiv_city", [(utc(2024, 6, 1, 10, 30), utc(2024, 6, 1, 11, 0))])
    assert is_active_in_hour(intervals, utc(2024, 6, 1, 10)) is True
    assert is_active_in_hour(intervals, utc(2024, 6, 1, 11)) is False


def test_exposure_label_open_left_window() -> None:
    zero_duration = intervals_df("kyiv_city", [(utc(2024, 6, 1, 10, 0), utc(2024, 6, 1, 10, 0))])
    origin = utc(2024, 6, 1, 10)
    assert exposure_in_forward_window(zero_duration, origin, 1) is False

    future_start = intervals_df("kyiv_city", [(utc(2024, 6, 1, 10, 0), utc(2024, 6, 1, 10, 30))])
    assert exposure_in_forward_window(future_start, utc(2024, 6, 1, 9), 1) is True


def test_exposure_label_ongoing_alert_counts_for_future_horizon() -> None:
    intervals = intervals_df(
        "kyiv_city",
        [(utc(2024, 6, 1, 8), utc(2024, 6, 1, 12))],
    )
    origin = utc(2024, 6, 1, 10)
    assert exposure_in_forward_window(intervals, origin, 1) is True
    assert exposure_in_forward_window(intervals, origin, 3) is True


def test_exposure_window_includes_alert_starting_at_origin_if_it_continues() -> None:
    """Alert that starts at origin and continues into (t, t+N] counts as exposure."""
    intervals = intervals_df(
        "kyiv_city",
        [(utc(2024, 6, 1, 10, 0), utc(2024, 6, 1, 10, 30))],
    )
    assert exposure_in_forward_window(intervals, utc(2024, 6, 1, 10), 1) is True


def test_nested_horizon_labels() -> None:
    intervals = intervals_df("kyiv_city", [(utc(2024, 6, 1, 11), utc(2024, 6, 1, 12))])
    origin = utc(2024, 6, 1, 10)
    labels = build_exposure_labels(intervals, [origin], horizons=[1, 3])
    assert labels.iloc[0][exposure_label(1)] == 1
    assert labels.iloc[0][exposure_label(3)] == 1


def test_build_hourly_panel_from_fixture(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    panel = build_hourly_panel(merged, utc(2024, 6, 1, 7), utc(2024, 6, 1, 14))
    assert len(panel) == 7
    active_hours = panel.loc[panel[PanelCol.ACTIVE] == 1, PanelCol.ORIGIN_HOUR].tolist()
    assert utc(2024, 6, 1, 8) in active_hours
    assert utc(2024, 6, 1, 9) in active_hours
    assert utc(2024, 6, 1, 7) not in active_hours


def test_build_exposure_labels_all_horizons(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    origins = pd.date_range(
        start=utc(2024, 6, 1, 7),
        end=utc(2024, 6, 1, 11),
        freq="h",
        tz="UTC",
    )
    labels = build_exposure_labels(merged, origins)
    horizon_cols = [c for c in labels.columns if is_exposure_label(c)]
    assert len(horizon_cols) == 24
