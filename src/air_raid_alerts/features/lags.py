"""Lag features from hourly panel (no future leakage)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from air_raid_alerts.schema import PanelCol


def sum_active_in_past_hours(panel: pd.DataFrame, origin_hour: datetime, lookback: int) -> int:
    """
    Sum of active flags for the lookback hours strictly before origin_hour.

    Features at origin t use only hours < t.
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")

    origin = pd.Timestamp(origin_hour).tz_convert("UTC")
    past = panel.loc[panel[PanelCol.ORIGIN_HOUR] < origin.to_pydatetime()].tail(lookback)
    return int(past[PanelCol.ACTIVE].sum())


def assert_features_use_no_future_panel_rows(
    panel: pd.DataFrame,
    origin_hour: datetime,
    lookback: int,
) -> None:
    """Raise AssertionError if any feature row would include origin_hour or later."""
    origin = pd.Timestamp(origin_hour).tz_convert("UTC").to_pydatetime()
    used = panel.loc[panel[PanelCol.ORIGIN_HOUR] < origin].tail(lookback)
    if not used.empty and used[PanelCol.ORIGIN_HOUR].max() >= origin:
        raise AssertionError("Feature lookback includes origin hour or future data")
    future = panel.loc[panel[PanelCol.ORIGIN_HOUR] >= origin]
    if not future.empty and used.index.intersection(future.index).any():
        raise AssertionError("Feature lookback overlaps future panel rows")
