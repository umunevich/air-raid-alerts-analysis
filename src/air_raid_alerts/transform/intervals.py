"""Filter, roll up, and merge alert intervals."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from air_raid_alerts.regions import RegionSpec, get_region
from air_raid_alerts.schema import EventCol, IntervalCol, MERGED_INTERVAL_COLUMNS
from air_raid_alerts.time_intervals import is_invalid_interval, is_outlier_interval_duration


def filter_region_events(events: pd.DataFrame, region_id: str) -> pd.DataFrame:
    """Keep rows matching the region registry oblast filter."""
    spec = get_region(region_id)
    mask = events[EventCol.OBLAST] == spec.vadimkin_oblast
    filtered = events.loc[mask].copy()
    filtered[EventCol.REGION_ID] = region_id
    return filtered.reset_index(drop=True)


def _to_interval_pairs(events: pd.DataFrame) -> list[tuple[datetime, datetime | None]]:
    return list(
        zip(
            events[EventCol.STARTED_AT],
            events[EventCol.FINISHED_AT],
            strict=True,
        )
    )


def merge_intervals(
    intervals: list[tuple[datetime, datetime | None]],
    *,
    data_cutoff: datetime | None = None,
) -> list[tuple[datetime, datetime]]:
    """
    Merge overlapping alert intervals.

    Alert active for all τ with started_at ≤ τ ≤ finished_at (inclusive end).
    Open-ended intervals (finished_at is None) are treated as active until
    data_cutoff when provided.
    """
    if not intervals:
        return []

    normalized: list[tuple[datetime, datetime]] = []
    for start, end in intervals:
        if end is None:
            if data_cutoff is None:
                raise ValueError("Open-ended interval requires data_cutoff")
            end = data_cutoff
        if is_invalid_interval(start, end):
            raise ValueError(f"finished_at < started_at: {start} > {end}")
        normalized.append((start, end))

    normalized.sort(key=lambda item: item[0])
    merged: list[tuple[datetime, datetime]] = [normalized[0]]

    for start, end in normalized[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def build_merged_intervals(
    events: pd.DataFrame,
    region_id: str,
    *,
    data_cutoff: datetime | None = None,
) -> pd.DataFrame:
    """
    Full interval pipeline: filter → optional oblast rollup → merge overlaps.

    Returns one row per disjoint merged interval with region_id set.
    """
    filtered = filter_region_events(events, region_id)
    if filtered.empty:
        return pd.DataFrame(columns=list(MERGED_INTERVAL_COLUMNS))

    pairs = _to_interval_pairs(filtered)
    merged = merge_intervals(pairs, data_cutoff=data_cutoff)

    rows = []
    for start, end in merged:
        outlier = is_outlier_interval_duration(start, end)
        rows.append(
            {
                IntervalCol.REGION_ID: region_id,
                IntervalCol.STARTED_AT: start,
                IntervalCol.FINISHED_AT: end,
                IntervalCol.IS_OUTLIER_DURATION: outlier,
            }
        )

    return pd.DataFrame(rows)


def rollup_mode_for_region(region_id: str) -> RegionSpec:
    return get_region(region_id)
