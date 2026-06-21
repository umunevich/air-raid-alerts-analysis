"""Orchestrate clean → intervals → panel → labels and write processed outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from air_raid_alerts.config import load_app_config
from air_raid_alerts.evaluation.splits import (
    SplitBoundaries,
    assign_split,
    compute_split_boundaries,
    is_in_primary_train,
)
from air_raid_alerts.paths import (
    raw_vadimkin_csv,
    raw_vadimkin_manifest,
    region_processed_dir,
)
from air_raid_alerts.regions import get_region
from air_raid_alerts.schema import IntervalCol, PanelCol, ProcessedCol, is_exposure_label
from air_raid_alerts.transform.clean import load_vadimkin_events
from air_raid_alerts.transform.intervals import build_merged_intervals
from air_raid_alerts.time_intervals import HOUR, hour_floor
from air_raid_alerts.transform.panel import build_exposure_labels, build_hourly_panel
from air_raid_alerts.features.build import (
    build_feature_matrix,
    build_training_matrix,
    feature_column_names,
    load_feature_config,
)
from air_raid_alerts.transform.qc import (
    load_manifest,
    validate_event_durations,
    validate_merged_intervals,
)

INTERVALS_FILENAME = "intervals.csv"
ORIGINS_FILENAME = "origins.csv"
FEATURES_FILENAME = "features.csv"
TRAINING_MATRIX_FILENAME = "training_matrix.csv"
MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True)
class ProcessResult:
    region_id: str
    output_dir: Path
    intervals: pd.DataFrame
    origins: pd.DataFrame
    features: pd.DataFrame
    training_matrix: pd.DataFrame
    manifest: dict


def _data_cutoff_from_intervals(intervals: pd.DataFrame) -> datetime:
    if intervals.empty:
        raise ValueError("Cannot determine data_cutoff from empty intervals")
    return intervals[IntervalCol.FINISHED_AT].max().to_pydatetime()


def _hourly_range(intervals: pd.DataFrame, data_cutoff: datetime) -> tuple[datetime, datetime]:
    range_start = hour_floor(intervals[IntervalCol.STARTED_AT].min().to_pydatetime())
    range_end = hour_floor(data_cutoff) + HOUR
    return range_start, range_end


def _annotate_splits(
    origins: pd.DataFrame,
    region_id: str,
    boundaries: SplitBoundaries,
) -> pd.DataFrame:
    annotated = origins.copy()
    annotated[ProcessedCol.SPLIT] = [
        assign_split(origin, boundaries) for origin in annotated[PanelCol.ORIGIN_HOUR]
    ]
    annotated[ProcessedCol.IN_PRIMARY_TRAIN] = [
        is_in_primary_train(origin, region_id, boundaries)
        for origin in annotated[PanelCol.ORIGIN_HOUR]
    ]
    return annotated


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _write_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)
        handle.write("\n")


def build_region_dataset(
    events: pd.DataFrame,
    region_id: str,
    *,
    validation_weeks: int | None = None,
    test_weeks: int | None = None,
    horizons: range | list[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Run transform steps in memory; return intervals, origins, features, training matrix, manifest."""
    get_region(region_id)
    config = load_app_config()
    val_weeks = validation_weeks if validation_weeks is not None else config.validation_weeks
    test_weeks_value = test_weeks if test_weeks is not None else config.test_weeks
    horizon_values = list(horizons) if horizons is not None else list(config.forecast_horizons)

    intervals = build_merged_intervals(events, region_id)
    duration_errors = validate_event_durations(intervals)
    merge_errors = validate_merged_intervals(intervals)
    if duration_errors or merge_errors:
        raise ValueError(
            "Interval QC failed: " + "; ".join(duration_errors + merge_errors)
        )

    data_cutoff = _data_cutoff_from_intervals(intervals)
    range_start, range_end = _hourly_range(intervals, data_cutoff)
    boundaries = compute_split_boundaries(
        data_cutoff,
        validation_weeks=val_weeks,
        test_weeks=test_weeks_value,
    )

    panel = build_hourly_panel(intervals, range_start, range_end)
    labels = build_exposure_labels(intervals, panel[PanelCol.ORIGIN_HOUR], horizons=horizon_values)
    origins = panel.merge(labels, on=[PanelCol.REGION_ID, PanelCol.ORIGIN_HOUR])
    origins = _annotate_splits(origins, region_id, boundaries)

    feature_config = load_feature_config()
    features = build_feature_matrix(
        origins,
        intervals,
        lag_hours=feature_config.lag_hours,
        display_timezone=feature_config.display_timezone,
    )
    training_matrix = build_training_matrix(features, origins)

    label_columns = [c for c in origins.columns if is_exposure_label(c)]
    manifest = {
        "region_id": region_id,
        "processed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "data_cutoff": data_cutoff.isoformat(),
        "hourly_range_start": range_start.isoformat(),
        "hourly_range_end": range_end.isoformat(),
        "interval_count": len(intervals),
        "origin_count": len(origins),
        "active_origin_count": int(origins[PanelCol.ACTIVE].sum()),
        "label_columns": label_columns,
        "feature_columns": feature_column_names(feature_config.lag_hours),
        "training_matrix_columns": list(training_matrix.columns),
        "split_boundaries": {
            "train_end": boundaries.train_end.isoformat(),
            "val_start": boundaries.val_start.isoformat(),
            "val_end": boundaries.val_end.isoformat(),
            "test_start": boundaries.test_start.isoformat(),
            "test_end": boundaries.test_end.isoformat(),
        },
        "validation_weeks": val_weeks,
        "test_weeks": test_weeks_value,
    }
    return intervals, origins, features, training_matrix, manifest


def process_region(
    region_id: str,
    *,
    raw_csv_path: Path | None = None,
    output_dir: Path | None = None,
    validation_weeks: int | None = None,
    test_weeks: int | None = None,
    horizons: range | list[int] | None = None,
) -> ProcessResult:
    """Load raw Vadimkin CSV, transform, and write processed artifacts for one region."""
    csv_path = raw_csv_path or raw_vadimkin_csv()
    out_dir = output_dir or region_processed_dir(region_id)

    if not csv_path.is_file():
        raise FileNotFoundError(f"Raw CSV not found: {csv_path}")

    events = load_vadimkin_events(csv_path, region_id=region_id)
    intervals, origins, features, training_matrix, manifest = build_region_dataset(
        events,
        region_id,
        validation_weeks=validation_weeks,
        test_weeks=test_weeks,
        horizons=horizons,
    )

    raw_manifest_path = raw_vadimkin_manifest()
    if raw_manifest_path.is_file():
        raw_manifest = load_manifest(raw_manifest_path)
        manifest["raw_source"] = {
            "path": str(csv_path),
            "git_sha": raw_manifest.get("git_sha"),
            "row_count": raw_manifest.get("row_count"),
            "downloaded_at": raw_manifest.get("downloaded_at"),
        }

    _write_csv(intervals, out_dir / INTERVALS_FILENAME)
    _write_csv(origins, out_dir / ORIGINS_FILENAME)
    _write_csv(features, out_dir / FEATURES_FILENAME)
    _write_csv(training_matrix, out_dir / TRAINING_MATRIX_FILENAME)
    _write_manifest(manifest, out_dir / MANIFEST_FILENAME)

    return ProcessResult(
        region_id=region_id,
        output_dir=out_dir,
        intervals=intervals,
        origins=origins,
        features=features,
        training_matrix=training_matrix,
        manifest=manifest,
    )
