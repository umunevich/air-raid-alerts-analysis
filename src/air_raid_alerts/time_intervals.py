"""Shared time and interval primitives (overlap, bounds, duration)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from air_raid_alerts.schema import IntervalCol

HOUR = timedelta(hours=1)
OUTLIER_DURATION = timedelta(days=7)
SECONDS_PER_HOUR = 3600.0


def hour_floor(ts: datetime) -> datetime:
    ts = ts.astimezone(UTC)
    return ts.replace(minute=0, second=0, microsecond=0)


def is_invalid_interval(start: datetime, end: datetime) -> bool:
    """True when ``finished_at`` is strictly before ``started_at``."""
    return end < start


def interval_duration(start: datetime, end: datetime) -> timedelta:
    return end - start


def is_outlier_interval_duration(start: datetime, end: datetime) -> bool:
    return interval_duration(start, end) > OUTLIER_DURATION


def is_outlier_event_duration(start: datetime, end: datetime | None) -> bool:
    if end is None:
        return False
    return is_outlier_interval_duration(start, end)


def duration_minutes(start: datetime, end: datetime | None) -> float | None:
    if end is None:
        return None
    return interval_duration(start, end).total_seconds() / 60.0


def overlaps_half_open(
    interval_start: datetime,
    interval_end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    """
    True when alert interval [interval_start, interval_end] overlaps window
    [window_start, window_end).
    """
    return interval_start < window_end and interval_end > window_start


def covers_instant(
    interval_start: datetime,
    interval_end: datetime,
    instant: datetime,
) -> bool:
    """True when the region is under alert at instant ``instant``."""
    return interval_start <= instant and interval_end > instant


def exposure_forward_overlap(
    interval_start: datetime,
    interval_end: datetime,
    origin: datetime,
    window_end: datetime,
) -> bool:
    """
    True when alert interval contributes to exposure in (origin, window_end].

    ``window_end`` is origin + N hours.
    """
    return interval_start <= window_end and interval_end > origin


def interval_bounds_ns(intervals: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    starts = pd.to_datetime(intervals[IntervalCol.STARTED_AT], utc=True).to_numpy(
        dtype="datetime64[ns]"
    )
    ends = pd.to_datetime(intervals[IntervalCol.FINISHED_AT], utc=True).to_numpy(dtype="datetime64[ns]")
    return starts, ends


def timestamps_to_ns(timestamps: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    return pd.to_datetime(timestamps, utc=True).to_numpy(dtype="datetime64[ns]")


def or_intervals_overlap_half_open(
    interval_starts: np.ndarray,
    interval_ends: np.ndarray,
    window_starts: np.ndarray,
    window_ends: np.ndarray,
    out: np.ndarray,
) -> None:
    for start, end in zip(interval_starts, interval_ends, strict=True):
        out |= ((start < window_ends) & (end > window_starts)).astype(np.int8)


def or_intervals_cover_instants(
    interval_starts: np.ndarray,
    interval_ends: np.ndarray,
    instants: np.ndarray,
    out: np.ndarray,
) -> None:
    for start, end in zip(interval_starts, interval_ends, strict=True):
        out |= ((start <= instants) & (end > instants)).astype(np.int8)


def or_intervals_exposure_forward(
    interval_starts: np.ndarray,
    interval_ends: np.ndarray,
    origin_starts: np.ndarray,
    window_ends: np.ndarray,
    out: np.ndarray,
) -> None:
    for start, end in zip(interval_starts, interval_ends, strict=True):
        out |= ((start <= window_ends) & (end > origin_starts)).astype(np.int8)


def hours_since_last_event(
    origin_ns: np.ndarray,
    event_times_ns: np.ndarray,
) -> np.ndarray:
    """Hours from the latest event at or before each origin; NaN when none exist."""
    if event_times_ns.size == 0:
        return np.full(len(origin_ns), np.nan, dtype=np.float64)

    sorted_events = np.sort(event_times_ns)
    indices = np.searchsorted(sorted_events, origin_ns, side="right") - 1
    hours = np.full(len(origin_ns), np.nan, dtype=np.float64)
    valid = indices >= 0
    delta = origin_ns[valid] - sorted_events[indices[valid]]
    hours[valid] = delta.astype("timedelta64[s]").astype(np.float64) / SECONDS_PER_HOUR
    return hours
