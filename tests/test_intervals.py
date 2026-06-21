"""Tests for interval filter, rollup, and merge."""

import pytest

from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.intervals import (
    build_merged_intervals,
    filter_region_events,
    merge_intervals,
)
from air_raid_alerts.schema import AdminLevel, EventCol, IntervalCol
from helpers import sample_vadimkin_path, utc


def test_filter_region_events_kyiv_city(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    filtered = filter_region_events(events, "kyiv_city")
    assert len(filtered) == 3
    assert (filtered[EventCol.OBLAST] == "Kyiv City").all()
    assert (filtered[EventCol.REGION_ID] == "kyiv_city").all()


def test_filter_region_events_kyivska_oblast_includes_subunits(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    filtered = filter_region_events(events, "kyivska_oblast")
    assert len(filtered) == 4
    assert set(filtered[EventCol.ADMIN_LEVEL]) == {AdminLevel.OBLAST, AdminLevel.RAION}


def test_merge_intervals_combines_overlaps() -> None:
    merged = merge_intervals(
        [
            (utc(2024, 6, 1, 8), utc(2024, 6, 1, 9, 30)),
            (utc(2024, 6, 1, 9), utc(2024, 6, 1, 10)),
        ]
    )
    assert len(merged) == 1
    assert merged[0] == (utc(2024, 6, 1, 8), utc(2024, 6, 1, 10))


def test_merge_intervals_keeps_disjoint() -> None:
    merged = merge_intervals(
        [
            (utc(2024, 6, 1, 8), utc(2024, 6, 1, 9)),
            (utc(2024, 6, 1, 12), utc(2024, 6, 1, 13)),
        ]
    )
    assert len(merged) == 2


def test_merge_intervals_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="finished_at < started_at"):
        merge_intervals([(utc(2024, 6, 1, 10), utc(2024, 6, 1, 9))])


def test_merge_intervals_open_ended_requires_cutoff() -> None:
    with pytest.raises(ValueError, match="data_cutoff"):
        merge_intervals([(utc(2024, 6, 1, 8), None)])


def test_build_merged_intervals_kyiv_city(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    assert len(merged) == 2
    assert merged.iloc[0][IntervalCol.STARTED_AT] == utc(2024, 6, 1, 8)
    assert merged.iloc[0][IntervalCol.FINISHED_AT] == utc(2024, 6, 1, 10)


def test_build_merged_intervals_oblast_rollup_same_start(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyivska_oblast")
    dec_rows = merged.loc[merged[IntervalCol.STARTED_AT] == utc(2025, 12, 5, 4)]
    assert len(dec_rows) == 1
    assert dec_rows.iloc[0][IntervalCol.FINISHED_AT] == utc(2025, 12, 5, 6)


def test_merge_intervals_open_ended_uses_cutoff() -> None:
    cutoff = utc(2024, 6, 1, 12)
    merged = merge_intervals([(utc(2024, 6, 1, 8), None)], data_cutoff=cutoff)
    assert merged == [(utc(2024, 6, 1, 8), cutoff)]


def test_kyiv_city_does_not_include_kyivska_oblast_rows(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    filtered = filter_region_events(events, "kyiv_city")
    assert "Kyivska oblast" not in filtered[EventCol.OBLAST].values


def test_build_merged_intervals_empty_for_unrepresented_oblast(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "lvivska_oblast")
    assert merged.empty


def test_merged_intervals_are_non_overlapping(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    for region_id in ("kyiv_city", "kyivska_oblast"):
        merged = build_merged_intervals(events, region_id)
        ends = merged[IntervalCol.FINISHED_AT].tolist()
        starts = merged[IntervalCol.STARTED_AT].tolist()
        for i in range(1, len(starts)):
            assert starts[i] > ends[i - 1]
