"""Hourly activity panel and exposure labels."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from air_raid_alerts.schema import (
    EventCol,
    IntervalCol,
    PANEL_COLUMNS,
    PanelCol,
    exposure_label,
)

HOUR = timedelta(hours=1)


def hour_floor(ts: datetime) -> datetime:
    ts = ts.astimezone(UTC)
    return ts.replace(minute=0, second=0, microsecond=0)


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
        start = row[IntervalCol.STARTED_AT]
        end = row[IntervalCol.FINISHED_AT]
        if start < hour_end and end > hour_start:
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
        start = row[IntervalCol.STARTED_AT]
        end = row[IntervalCol.FINISHED_AT]
        # Overlap of [start, end] with (origin, window_end]
        if start <= window_end and end > origin:
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
    rows = []
    for origin in origins:
        origin_dt = origin.to_pydatetime()
        rows.append(
            {
                PanelCol.REGION_ID: region_id,
                PanelCol.ORIGIN_HOUR: origin_dt,
                PanelCol.ACTIVE: int(is_active_in_hour(intervals, origin_dt)),
            }
        )
    return pd.DataFrame(rows)


def build_exposure_labels(
    intervals: pd.DataFrame,
    origins: pd.DatetimeIndex | pd.Series,
    horizons: range | list[int] | None = None,
) -> pd.DataFrame:
    """Build y_r,N for each origin hour and horizon N."""
    if horizons is None:
        horizons = range(1, 25)

    rows = []
    region_id = intervals[IntervalCol.REGION_ID].iloc[0] if not intervals.empty else None
    for origin in origins:
        origin_dt = pd.Timestamp(origin).to_pydatetime()
        row: dict = {PanelCol.REGION_ID: region_id, PanelCol.ORIGIN_HOUR: origin_dt}
        for horizon in horizons:
            row[exposure_label(horizon)] = int(
                exposure_in_forward_window(intervals, origin_dt, horizon)
            )
        rows.append(row)

    return pd.DataFrame(rows)
