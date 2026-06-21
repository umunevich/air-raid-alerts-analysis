"""Tests for Vadimkin → canonical mapping."""

from datetime import timedelta

import pandas as pd
import pytest

from air_raid_alerts.transform.clean import (
    granularity_era,
    is_outlier_duration,
    load_vadimkin_events,
    make_alert_id,
    map_vadimkin_row,
)
from air_raid_alerts.schema import EventCol, VadimkinCol
from helpers import sample_vadimkin_path, utc


def test_make_alert_id_is_stable() -> None:
    start = utc(2024, 6, 1, 8)
    end = utc(2024, 6, 1, 9)
    first = make_alert_id("Kyiv City", "", "", "oblast", start, end)
    second = make_alert_id("Kyiv City", "", "", "oblast", start, end)
    assert first == second
    assert len(first) == 16


def test_granularity_era_oblast_dominant() -> None:
    assert granularity_era(utc(2024, 1, 1), "oblast") == "oblast_dominant"


def test_granularity_era_raion_dominant() -> None:
    assert granularity_era(utc(2026, 1, 1), "raion") == "raion_dominant"


def test_granularity_era_mixed() -> None:
    assert granularity_era(utc(2026, 1, 1), "oblast") == "mixed"


def test_is_outlier_duration_flags_long_intervals() -> None:
    start = utc(2024, 1, 1)
    end = start + timedelta(days=8)
    assert is_outlier_duration(start, end) is True


def test_load_vadimkin_events_maps_schema(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    assert len(events) == 8
    assert set(events.columns) >= {
        EventCol.ALERT_ID,
        EventCol.STARTED_AT,
        EventCol.FINISHED_AT,
        EventCol.GRANULARITY_ERA,
        EventCol.IS_OUTLIER_DURATION,
        EventCol.ADMIN_LEVEL,
    }
    assert all(ts.tzinfo is not None for ts in events[EventCol.STARTED_AT])


def test_load_vadimkin_events_rejects_bad_header(tmp_path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected Vadimkin header"):
        load_vadimkin_events(bad)


def test_alert_ids_are_unique_in_fixture(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    assert events[EventCol.ALERT_ID].is_unique


def test_map_vadimkin_row_handles_missing_finished_at() -> None:
    row = pd.Series(
        {
            VadimkinCol.OBLAST: "Kyiv City",
            VadimkinCol.RAION: "",
            VadimkinCol.HROMADA: "",
            VadimkinCol.LEVEL: "oblast",
            VadimkinCol.STARTED_AT: "2024-06-01 08:00:00+00:00",
            VadimkinCol.FINISHED_AT: pd.NA,
            VadimkinCol.SOURCE: "official",
        }
    )
    mapped = map_vadimkin_row(row)
    assert mapped[EventCol.FINISHED_AT] is None
    assert mapped[EventCol.IS_OUTLIER_DURATION] is False
