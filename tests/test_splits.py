"""Tests for time-based splits."""

from datetime import timedelta

import pytest

from air_raid_alerts.evaluation.splits import (
    assign_split,
    compute_split_boundaries,
    is_in_primary_train,
    primary_train_start,
)
from air_raid_alerts.regions import REGION_REGISTRY
from helpers import utc


def test_compute_split_boundaries_example_from_data_md() -> None:
    cutoff = utc(2026, 6, 20)
    bounds = compute_split_boundaries(cutoff, validation_weeks=8, test_weeks=4)
    assert bounds.test_end == cutoff
    assert bounds.test_start == utc(2026, 5, 23)
    assert bounds.val_end == utc(2026, 5, 23)
    assert bounds.val_start == utc(2026, 3, 28)
    assert bounds.train_end == utc(2026, 3, 28)


def test_assign_split_respects_time_order() -> None:
    bounds = compute_split_boundaries(utc(2026, 6, 20))
    assert assign_split(utc(2026, 3, 1), bounds) == "train"
    assert assign_split(utc(2026, 4, 15), bounds) == "validation"
    assert assign_split(utc(2026, 6, 1), bounds) == "test"


def test_primary_train_window_kyiv_city_18_months() -> None:
    val_start = utc(2026, 3, 28)
    start = primary_train_start("kyiv_city", val_start)
    assert start == val_start - timedelta(days=30 * 18)


def test_is_in_primary_train_subset_of_train() -> None:
    bounds = compute_split_boundaries(utc(2026, 6, 20))
    old_origin = utc(2022, 1, 1)
    assert assign_split(old_origin, bounds) == "train"
    assert is_in_primary_train(old_origin, "kyiv_city", bounds) is False

    recent_origin = utc(2025, 6, 1)
    assert assign_split(recent_origin, bounds) == "train"
    assert is_in_primary_train(recent_origin, "kyiv_city", bounds) is True


def test_split_boundary_at_train_end_is_train() -> None:
    bounds = compute_split_boundaries(utc(2026, 6, 20))
    assert assign_split(bounds.train_end, bounds) == "train"


@pytest.mark.parametrize(
    ("region_id", "months"),
    [
        (rid, spec.primary_train_months)
        for rid, spec in REGION_REGISTRY.items()
        if not spec.excluded and spec.primary_train_months is not None
    ],
)
def test_primary_train_months_match_data_md(region_id: str, months: int) -> None:
    assert months in {12, 18, 24}
    val_start = utc(2026, 3, 28)
    start = primary_train_start(region_id, val_start)
    assert start < val_start
