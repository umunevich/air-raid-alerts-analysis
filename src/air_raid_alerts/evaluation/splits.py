"""Time-based train / validation / test boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from air_raid_alerts.config import load_app_config
from air_raid_alerts.regions import get_region
from air_raid_alerts.schema import SplitName


@dataclass(frozen=True)
class SplitBoundaries:
    train_end: datetime
    val_start: datetime
    val_end: datetime
    test_start: datetime
    test_end: datetime


def compute_split_boundaries(
    data_cutoff: datetime,
    *,
    validation_weeks: int | None = None,
    test_weeks: int | None = None,
) -> SplitBoundaries:
    """Compute global val/test windows anchored at data_cutoff."""
    config = load_app_config()
    val_weeks = validation_weeks if validation_weeks is not None else config.validation_weeks
    test_weeks_value = test_weeks if test_weeks is not None else config.test_weeks
    cutoff = data_cutoff.astimezone(UTC)
    test_end = cutoff
    test_start = cutoff - timedelta(weeks=test_weeks_value)
    val_end = test_start
    val_start = val_end - timedelta(weeks=val_weeks)
    train_end = val_start
    return SplitBoundaries(
        train_end=train_end,
        val_start=val_start,
        val_end=val_end,
        test_start=test_start,
        test_end=test_end,
    )


def primary_train_start(region_id: str, val_start: datetime) -> datetime:
    """Primary train window start per DATA.md region table."""
    spec = get_region(region_id)
    months = spec.primary_train_months
    if months is None:
        raise ValueError(f"No primary train window for {region_id}")
    return val_start - timedelta(days=30 * months)


def assign_split(origin_hour: datetime, boundaries: SplitBoundaries) -> str:
    """Assign an hourly origin to train, validation, or test."""
    t = origin_hour.astimezone(UTC)
    if boundaries.test_start < t <= boundaries.test_end:
        return SplitName.TEST
    if boundaries.val_start < t <= boundaries.val_end:
        return SplitName.VALIDATION
    if t <= boundaries.train_end:
        return SplitName.TRAIN
    return SplitName.HOLDOUT


def is_in_primary_train(
    origin_hour: datetime,
    region_id: str,
    boundaries: SplitBoundaries,
) -> bool:
    """True if origin is in the region-specific primary train window and before val."""
    t = origin_hour.astimezone(UTC)
    if t > boundaries.train_end:
        return False
    return t >= primary_train_start(region_id, boundaries.val_start)
