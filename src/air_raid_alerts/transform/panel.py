"""Hourly activity panel and exposure labels."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from air_raid_alerts.schema import (
    IntervalCol,
    PANEL_COLUMNS,
    PanelCol,
    exposure_label,
)
from air_raid_alerts.time_intervals import (
    HOUR,
    exposure_forward_overlap,
    hour_floor,
    interval_bounds_ns,
    or_intervals_exposure_forward,
    or_intervals_overlap_half_open,
    overlaps_half_open,
)

__all__ = [
    "build_exposure_labels",
    "build_hourly_origins",
    "build_hourly_panel",
    "exposure_in_forward_window",
    "hour_floor",
    "is_active_in_hour",
]


def is_active_in_hour(
    intervals: pd.DataFrame,
    hour_start: datetime,
) -> bool:
    """
    Hourly active(r, t) with convention [t, t+1h).

    True if ∃ τ with started_at ≤ τ ≤ finished_at and τ ∈ [hour_start, hour_start + 1h).
    """
    hour_end = hour_start + HOUR
    for _, row in intervals.iterrows():
        if overlaps_half_open(
            row[IntervalCol.STARTED_AT],
            row[IntervalCol.FINISHED_AT],
            hour_start,
            hour_end,
        ):
            return True
    return False


def exposure_in_forward_window(
    intervals: pd.DataFrame,
    origin: datetime,
    horizon_hours: int,
) -> bool:
    """
    y_r,N(t) = 1 if ∃ τ ∈ (t, t+N] with region under alert.

    Uses inclusive alert end and open-left forecast window per REQUIREMENTS.md.
    """
    if horizon_hours < 1:
        raise ValueError("horizon_hours must be >= 1")

    window_end = origin + timedelta(hours=horizon_hours)
    for _, row in intervals.iterrows():
        if exposure_forward_overlap(
            row[IntervalCol.STARTED_AT],
            row[IntervalCol.FINISHED_AT],
            origin,
            window_end,
        ):
            return True
    return False


def build_hourly_origins(
    range_start: datetime,
    range_end: datetime,
) -> pd.DatetimeIndex:
    """Hourly forecast origins from range_start (inclusive) to range_end (exclusive)."""
    start = hour_floor(range_start)
    end = hour_floor(range_end)
    if end <= start:
        return pd.DatetimeIndex([], tz="UTC")
    return pd.date_range(start=start, end=end - HOUR, freq="h", tz="UTC")


def build_hourly_panel(
    intervals: pd.DataFrame,
    range_start: datetime,
    range_end: datetime,
) -> pd.DataFrame:
    """Build hourly active flags for merged intervals."""
    origins = build_hourly_origins(range_start, range_end)
    if len(origins) == 0:
        return pd.DataFrame(columns=list(PANEL_COLUMNS))

    region_id = intervals[IntervalCol.REGION_ID].iloc[0] if not intervals.empty else None
    if intervals.empty:
        return pd.DataFrame(
            {
                PanelCol.REGION_ID: region_id,
                PanelCol.ORIGIN_HOUR: origins.to_pydatetime(),
                PanelCol.ACTIVE: 0,
            }
        )

    hour_starts = origins.to_numpy(dtype="datetime64[ns]")
    hour_ends = hour_starts + np.timedelta64(1, "h")
    starts, ends = interval_bounds_ns(intervals)

    active = np.zeros(len(hour_starts), dtype=np.int8)
    or_intervals_overlap_half_open(starts, ends, hour_starts, hour_ends, active)

    return pd.DataFrame(
        {
            PanelCol.REGION_ID: region_id,
            PanelCol.ORIGIN_HOUR: origins.to_pydatetime(),
            PanelCol.ACTIVE: active,
        }
    )


def build_exposure_labels(
    intervals: pd.DataFrame,
    origins: pd.DatetimeIndex | pd.Series,
    horizons: range | list[int] | None = None,
) -> pd.DataFrame:
    """Build y_r,N for each origin hour and horizon N."""
    if horizons is None:
        horizons = range(1, 25)

    origin_index = pd.DatetimeIndex(origins, tz="UTC")
    region_id = intervals[IntervalCol.REGION_ID].iloc[0] if not intervals.empty else None
    origin_hours = origin_index.to_pydatetime()

    data: dict = {
        PanelCol.REGION_ID: region_id,
        PanelCol.ORIGIN_HOUR: origin_hours,
    }

    if intervals.empty:
        for horizon in horizons:
            data[exposure_label(horizon)] = 0
        return pd.DataFrame(data)

    origin_starts = origin_index.to_numpy(dtype="datetime64[ns]")
    starts, ends = interval_bounds_ns(intervals)

    for horizon in horizons:
        window_ends = origin_starts + np.timedelta64(horizon, "h")
        exposed = np.zeros(len(origin_starts), dtype=np.int8)
        or_intervals_exposure_forward(starts, ends, origin_starts, window_ends, exposed)
        data[exposure_label(horizon)] = exposed

    return pd.DataFrame(data)
