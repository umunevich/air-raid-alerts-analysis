"""Optional integration tests against the full local Vadimkin snapshot."""

import pytest

from air_raid_alerts.paths import project_root, raw_vadimkin_dir
from air_raid_alerts.regions import list_allowlisted_regions
from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.intervals import build_merged_intervals
from air_raid_alerts.transform.qc import (
    validate_event_durations,
    validate_merged_intervals,
    validate_raw_against_manifest,
)

RAW_CSV = raw_vadimkin_dir() / "official_data_en.csv"
MANIFEST = raw_vadimkin_dir() / "manifest.json"


pytestmark = pytest.mark.skipif(
    not RAW_CSV.is_file() or not MANIFEST.is_file(),
    reason="Full Vadimkin snapshot not present locally",
)


def test_local_raw_passes_manifest_qc() -> None:
    errors = validate_raw_against_manifest(RAW_CSV, MANIFEST)
    assert errors == []


@pytest.mark.parametrize("region_id", list_allowlisted_regions())
def test_each_allowlisted_region_builds_merged_intervals(region_id: str) -> None:
    events = load_vadimkin_events(RAW_CSV)
    merged = build_merged_intervals(events, region_id)
    assert validate_merged_intervals(merged) == []
    assert len(merged) > 0


def test_local_events_have_no_negative_durations() -> None:
    events = load_vadimkin_events(RAW_CSV)
    assert validate_event_durations(events) == []
