"""End-to-end pipeline tests on fixture data."""

from air_raid_alerts.evaluation.splits import assign_split, compute_split_boundaries
from air_raid_alerts.schema import IntervalCol, PanelCol, exposure_label
from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.intervals import build_merged_intervals
from air_raid_alerts.transform.panel import build_exposure_labels, build_hourly_panel
from air_raid_alerts.transform.qc import validate_raw_against_manifest
from helpers import sample_manifest_path, sample_vadimkin_path, utc


def test_full_pipeline_kyiv_city(sample_vadimkin_path, sample_manifest_path) -> None:
    assert validate_raw_against_manifest(sample_vadimkin_path, sample_manifest_path) == []

    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    panel = build_hourly_panel(merged, utc(2024, 6, 1, 7), utc(2024, 6, 1, 14))
    labels = build_exposure_labels(
        merged,
        panel[PanelCol.ORIGIN_HOUR],
        horizons=[1, 6, 24],
    )

    assert len(merged) >= 1
    assert len(panel) == len(labels)
    assert exposure_label(1) in labels.columns


def test_full_pipeline_kyivska_oblast_rollup(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyivska_oblast")
    assert len(merged) >= 2
    dec = merged.loc[merged[IntervalCol.STARTED_AT] == utc(2025, 12, 5, 4)]
    assert len(dec) == 1


def test_pipeline_assigns_splits_on_panel(sample_vadimkin_path) -> None:
    events = load_vadimkin_events(sample_vadimkin_path)
    merged = build_merged_intervals(events, "kyiv_city")
    panel = build_hourly_panel(merged, utc(2024, 6, 1, 0), utc(2024, 6, 3, 0))
    bounds = compute_split_boundaries(utc(2024, 6, 2, 12))
    splits = {assign_split(row.origin_hour, bounds) for row in panel.itertuples()}
    assert splits <= {"train", "validation", "test", "holdout"}
