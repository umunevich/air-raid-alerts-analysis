"""Tests for region processing pipeline orchestration."""

import json
from pathlib import Path

import pytest

from air_raid_alerts.paths import region_processed_dir
from air_raid_alerts.schema import (
    IntervalCol,
    PanelCol,
    ProcessedCol,
    is_exposure_label,
)
from air_raid_alerts.transform.pipeline import (
    FEATURES_FILENAME,
    INTERVALS_FILENAME,
    MANIFEST_FILENAME,
    ORIGINS_FILENAME,
    TRAINING_MATRIX_FILENAME,
    build_region_dataset,
    process_region,
)
from air_raid_alerts.transform.qc import validate_merged_intervals
from helpers import sample_vadimkin_path


def test_build_region_dataset_kyiv_city(sample_vadimkin_path) -> None:
    from air_raid_alerts.transform.clean import load_vadimkin_events

    events = load_vadimkin_events(sample_vadimkin_path)
    intervals, origins, features, training_matrix, manifest = build_region_dataset(events, "kyiv_city")

    assert len(intervals) == 2
    assert validate_merged_intervals(intervals) == []
    assert len(origins) > 0
    assert len(features) == len(origins)
    assert len(training_matrix) == len(origins)
    assert PanelCol.ACTIVE in origins.columns
    assert ProcessedCol.SPLIT in origins.columns
    assert ProcessedCol.IN_PRIMARY_TRAIN in origins.columns
    assert sum(is_exposure_label(c) for c in origins.columns) == 24
    assert manifest["region_id"] == "kyiv_city"
    assert manifest["interval_count"] == 2


def test_process_region_writes_artifacts(sample_vadimkin_path, tmp_path: Path) -> None:
    out_dir = tmp_path / "kyiv_city"
    result = process_region(
        "kyiv_city",
        raw_csv_path=sample_vadimkin_path,
        output_dir=out_dir,
    )

    assert result.output_dir == out_dir
    assert (out_dir / INTERVALS_FILENAME).is_file()
    assert (out_dir / ORIGINS_FILENAME).is_file()
    assert (out_dir / FEATURES_FILENAME).is_file()
    assert (out_dir / TRAINING_MATRIX_FILENAME).is_file()
    assert (out_dir / MANIFEST_FILENAME).is_file()

    with (out_dir / MANIFEST_FILENAME).open(encoding="utf-8") as handle:
        written_manifest = json.load(handle)

    assert written_manifest["region_id"] == "kyiv_city"
    assert written_manifest["origin_count"] == len(result.origins)
    assert "split_boundaries" in written_manifest


def test_process_region_missing_raw_csv(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Raw CSV not found"):
        process_region(
            "kyiv_city",
            raw_csv_path=tmp_path / "missing.csv",
            output_dir=tmp_path / "kyiv_city",
        )


def test_default_output_dir_uses_processed_tree() -> None:
    assert region_processed_dir("kyiv_city").name == "kyiv_city"
    assert region_processed_dir("kyiv_city").parent.name == "processed"
