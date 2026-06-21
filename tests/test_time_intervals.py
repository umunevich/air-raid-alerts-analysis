"""Tests for shared time and interval primitives."""

import numpy as np
import pandas as pd

from air_raid_alerts.time_intervals import (
    covers_instant,
    exposure_forward_overlap,
    hours_since_last_event,
    is_invalid_interval,
    is_outlier_event_duration,
    is_outlier_interval_duration,
    overlaps_half_open,
)
from helpers import utc


def test_is_invalid_interval() -> None:
    assert is_invalid_interval(utc(2024, 6, 1, 10), utc(2024, 6, 1, 9)) is True
    assert is_invalid_interval(utc(2024, 6, 1, 9), utc(2024, 6, 1, 10)) is False


def test_outlier_duration_helpers() -> None:
    start = utc(2024, 1, 1)
    short_end = start.replace(day=2)
    long_end = start.replace(day=10)
    assert is_outlier_interval_duration(start, long_end) is True
    assert is_outlier_interval_duration(start, short_end) is False
    assert is_outlier_event_duration(start, None) is False


def test_overlaps_half_open_matches_panel_convention() -> None:
    start = utc(2024, 6, 1, 10, 30)
    end = utc(2024, 6, 1, 11, 0)
    assert overlaps_half_open(start, end, utc(2024, 6, 1, 10), utc(2024, 6, 1, 11)) is True
    assert overlaps_half_open(start, end, utc(2024, 6, 1, 11), utc(2024, 6, 1, 12)) is False


def test_covers_instant_and_exposure_forward() -> None:
    start = utc(2024, 6, 1, 8)
    end = utc(2024, 6, 1, 10)
    origin = utc(2024, 6, 1, 9)
    assert covers_instant(start, end, origin) is True
    assert covers_instant(start, end, end) is False
    assert exposure_forward_overlap(start, end, utc(2024, 6, 1, 7), utc(2024, 6, 1, 8)) is True
    assert exposure_forward_overlap(start, end, utc(2024, 6, 1, 10), utc(2024, 6, 1, 11)) is False


def test_hours_since_last_event() -> None:
    origin_ns = pd.to_datetime([utc(2024, 6, 1, 9)], utc=True).to_numpy(dtype="datetime64[ns]")
    starts = pd.to_datetime([utc(2024, 6, 1, 8)], utc=True).to_numpy(dtype="datetime64[ns]")
    ends = pd.to_datetime([utc(2024, 6, 1, 10)], utc=True).to_numpy(dtype="datetime64[ns]")
    assert hours_since_last_event(origin_ns, starts)[0] == 1.0
    assert pd.isna(hours_since_last_event(origin_ns, ends)[0])
