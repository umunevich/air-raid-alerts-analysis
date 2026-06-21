"""Column names and schema constants shared across the pipeline."""

from __future__ import annotations


class VadimkinCol:
    OBLAST = "oblast"
    RAION = "raion"
    HROMADA = "hromada"
    LEVEL = "level"
    STARTED_AT = "started_at"
    FINISHED_AT = "finished_at"
    SOURCE = "source"


VADIMKIN_COLUMNS: tuple[str, ...] = (
    VadimkinCol.OBLAST,
    VadimkinCol.RAION,
    VadimkinCol.HROMADA,
    VadimkinCol.LEVEL,
    VadimkinCol.STARTED_AT,
    VadimkinCol.FINISHED_AT,
    VadimkinCol.SOURCE,
)

# Backward-compatible alias used by ingest and manifest validation.
EXPECTED_COLUMNS = VADIMKIN_COLUMNS


class AdminLevel:
    OBLAST = "oblast"
    RAION = "raion"
    HROMADA = "hromada"


class EventCol:
    ALERT_ID = "alert_id"
    REGION_ID = "region_id"
    OBLAST = VadimkinCol.OBLAST
    RAION = VadimkinCol.RAION
    HROMADA = VadimkinCol.HROMADA
    ADMIN_LEVEL = "admin_level"
    STARTED_AT = VadimkinCol.STARTED_AT
    FINISHED_AT = VadimkinCol.FINISHED_AT
    GRANULARITY_ERA = "granularity_era"
    IS_OUTLIER_DURATION = "is_outlier_duration"
    SOURCE = VadimkinCol.SOURCE


class IntervalCol:
    REGION_ID = EventCol.REGION_ID
    STARTED_AT = EventCol.STARTED_AT
    FINISHED_AT = EventCol.FINISHED_AT
    IS_OUTLIER_DURATION = EventCol.IS_OUTLIER_DURATION


MERGED_INTERVAL_COLUMNS: tuple[str, ...] = (
    IntervalCol.REGION_ID,
    IntervalCol.STARTED_AT,
    IntervalCol.FINISHED_AT,
    IntervalCol.IS_OUTLIER_DURATION,
)


class PanelCol:
    REGION_ID = EventCol.REGION_ID
    ORIGIN_HOUR = "origin_hour"
    ACTIVE = "active"


class ProcessedCol:
    SPLIT = "split"
    IN_PRIMARY_TRAIN = "in_primary_train"


class SplitName:
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    HOLDOUT = "holdout"


class FeatureCol:
    ACTIVE_AT_ORIGIN = "active_at_origin"
    TIME_SINCE_LAST_START_H = "time_since_last_start_h"
    TIME_SINCE_LAST_END_H = "time_since_last_end_h"
    HOUR_KYIV = "hour_kyiv"
    DAY_OF_WEEK_KYIV = "dow_kyiv"
    HOUR_OF_WEEK_KYIV = "hour_of_week_kyiv"


def active_sum_column(lookback_hours: int) -> str:
    return f"active_sum_{lookback_hours}h"


PANEL_COLUMNS: tuple[str, ...] = (
    PanelCol.REGION_ID,
    PanelCol.ORIGIN_HOUR,
    PanelCol.ACTIVE,
)

EXPOSURE_LABEL_PREFIX = "y_"


def exposure_label(horizon_hours: int) -> str:
    return f"{EXPOSURE_LABEL_PREFIX}{horizon_hours}"


def is_exposure_label(column_name: str) -> bool:
    return column_name.startswith(EXPOSURE_LABEL_PREFIX)


def label_horizons(labels) -> list[int]:
    columns = labels.columns if hasattr(labels, "columns") else labels
    return sorted(
        int(column.removeprefix(EXPOSURE_LABEL_PREFIX))
        for column in columns
        if is_exposure_label(column)
    )


__all__ = [
    "AdminLevel",
    "EventCol",
    "EXPECTED_COLUMNS",
    "FeatureCol",
    "IntervalCol",
    "MERGED_INTERVAL_COLUMNS",
    "PANEL_COLUMNS",
    "PanelCol",
    "ProcessedCol",
    "SplitName",
    "VADIMKIN_COLUMNS",
    "VadimkinCol",
    "active_sum_column",
    "exposure_label",
    "is_exposure_label",
    "label_horizons",
]
