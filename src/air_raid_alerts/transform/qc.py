"""Raw and transformed data quality checks."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from air_raid_alerts.ingest.fetch_vadimkin import validate_csv
from air_raid_alerts.schema import (
    EXPECTED_COLUMNS,
    EventCol,
    IntervalCol,
    exposure_label,
)
from air_raid_alerts.time_intervals import is_invalid_interval
from air_raid_alerts.transform.clean import load_vadimkin_events


def load_manifest(manifest_path: Path) -> dict:
    with manifest_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_raw_against_manifest(
    csv_path: Path,
    manifest_path: Path,
    *,
    row_count_tolerance: float = 0.01,
) -> list[str]:
    """Return a list of validation errors (empty if OK)."""
    errors: list[str] = []
    manifest = load_manifest(manifest_path)

    expected_columns = manifest.get("columns", list(EXPECTED_COLUMNS))
    if list(expected_columns) != list(EXPECTED_COLUMNS):
        errors.append("Manifest columns do not match expected Vadimkin schema")

    try:
        row_count = validate_csv(csv_path)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    manifest_rows = manifest.get("row_count")
    if manifest_rows is not None:
        delta = abs(row_count - manifest_rows) / max(manifest_rows, 1)
        if delta > row_count_tolerance:
            errors.append(
                f"Row count {row_count} differs from manifest {manifest_rows} "
                f"by {delta:.2%} (tolerance {row_count_tolerance:.0%})"
            )

    return errors


def validate_event_durations(events: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    for idx, row in events.iterrows():
        finished = row[EventCol.FINISHED_AT]
        if finished is not None and is_invalid_interval(row[EventCol.STARTED_AT], finished):
            errors.append(f"Row {idx}: finished_at < started_at")
    return errors


def validate_merged_intervals(intervals: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if intervals.empty:
        return errors

    previous_end = None
    for idx, row in intervals.iterrows():
        if is_invalid_interval(row[IntervalCol.STARTED_AT], row[IntervalCol.FINISHED_AT]):
            errors.append(f"Interval {idx}: finished_at < started_at")
        if previous_end is not None and row[IntervalCol.STARTED_AT] <= previous_end:
            errors.append(f"Interval {idx}: overlaps previous merged interval")
        previous_end = row[IntervalCol.FINISHED_AT]

    return errors


def assert_labels_match_intervals(
    intervals: pd.DataFrame,
    origin_hour: datetime,
    horizon_hours: int,
    label_value: int,
) -> None:
    """
    Verify y_r,N(t) is consistent with merged intervals and DATA.md window (t, t+N].

    Labels may use alert state after origin t (exposure target); this checks
    consistency of the label function, not feature leakage.
    """
    from air_raid_alerts.transform.panel import exposure_in_forward_window

    expected = int(exposure_in_forward_window(intervals, origin_hour, horizon_hours))
    if expected != label_value:
        raise AssertionError(
            f"Label {exposure_label(horizon_hours)} at {origin_hour} "
            f"expected {expected}, got {label_value}"
        )
