"""Tests for data quality checks."""

import json

import pandas as pd
import pytest

from air_raid_alerts.features.build import build_feature_matrix
from air_raid_alerts.schema import EventCol, FeatureCol, IntervalCol, PanelCol, active_sum_column, exposure_label
from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.intervals import build_merged_intervals
from air_raid_alerts.transform.panel import build_exposure_labels, build_hourly_panel
from air_raid_alerts.transform.qc import (
    assert_labels_match_intervals,
    validate_event_durations,
    validate_merged_intervals,
    validate_raw_against_manifest,
)
from helpers import sample_manifest_path, sample_vadimkin_path, utc, vadimkin_columns_json


def test_validate_raw_against_manifest_ok(sample_vadimkin_path, sample_manifest_path) -> None:
    errors = validate_raw_against_manifest(sample_vadimkin_path, sample_manifest_path)
    assert errors == []


def test_validate_raw_against_manifest_row_count_mismatch(
    sample_vadimkin_path,
    sample_manifest_path,
    tmp_path,
) -> None:
    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text(
        json.dumps({"row_count": 100, "columns": vadimkin_columns_json()}),
        encoding="utf-8",
    )
    errors = validate_raw_against_manifest(sample_vadimkin_path, bad_manifest)
    assert any("Row count" in err for err in errors)


def test_validate_event_durations_detects_negative() -> None:
    events = pd.DataFrame(
        {
            EventCol.STARTED_AT: [utc(2024, 1, 2)],
            EventCol.FINISHED_AT: [utc(2024, 1, 1)],
        }
    )
    errors = validate_event_durations(events)
    assert len(errors) == 1


def test_validate_merged_intervals_detects_overlap() -> None:
    intervals = pd.DataFrame(
        {
            IntervalCol.STARTED_AT: [utc(2024, 1, 1, 10), utc(2024, 1, 1, 10, 30)],
            IntervalCol.FINISHED_AT: [utc(2024, 1, 1, 11), utc(2024, 1, 1, 12)],
        }
    )
    errors = validate_merged_intervals(intervals)
    assert any("overlaps" in err for err in errors)


def test_validate_raw_against_manifest_bad_header(tmp_path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("a,b\n1,2\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"row_count": 1, "columns": vadimkin_columns_json()}),
        encoding="utf-8",
    )
    errors = validate_raw_against_manifest(bad_csv, manifest)
    assert any("Unexpected CSV header" in err for err in errors)


def test_lag_features_do_not_use_future_hours(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    panel = build_hourly_panel(merged, utc(2024, 6, 1, 7), utc(2024, 6, 1, 14))
    origin = utc(2024, 6, 1, 10)
    features = build_feature_matrix(panel, merged, lag_hours=[3])
    row = features.loc[features[PanelCol.ORIGIN_HOUR] == origin].iloc[0]
    expected = int(panel.loc[panel[PanelCol.ORIGIN_HOUR] < origin].tail(3)[PanelCol.ACTIVE].sum())
    assert row[active_sum_column(3)] == expected
    assert row[FeatureCol.ACTIVE_AT_ORIGIN] in (0, 1)


def test_labels_consistent_with_exposure_definition(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    origin = utc(2024, 6, 1, 10)
    labels = build_exposure_labels(merged, [origin], horizons=[1, 6])
    assert_labels_match_intervals(merged, origin, 1, labels.iloc[0][exposure_label(1)])
    assert_labels_match_intervals(merged, origin, 6, labels.iloc[0][exposure_label(6)])


def test_merged_output_passes_qc(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    assert validate_merged_intervals(merged) == []
    assert validate_event_durations(merged) == []
