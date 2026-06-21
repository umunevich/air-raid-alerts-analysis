"""Map Vadimkin raw rows to canonical event records."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pandas as pd

from air_raid_alerts.regions import get_region
from air_raid_alerts.schema import (
    AdminLevel,
    EventCol,
    VADIMKIN_COLUMNS,
    VadimkinCol,
)
from air_raid_alerts.time_intervals import is_outlier_event_duration as is_outlier_duration

GRANULARITY_ERA_CUTOFF = datetime(2025, 12, 1, tzinfo=UTC)


def parse_utc_timestamp(value: str) -> datetime:
    """Parse Vadimkin ISO-like UTC timestamps."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def make_alert_id(
    oblast: str,
    raion: str,
    hromada: str,
    level: str,
    started_at: datetime,
    finished_at: datetime | None,
) -> str:
    finished_token = finished_at.isoformat() if finished_at is not None else ""
    payload = (
        f"{oblast}|{raion}|{hromada}|{level}|"
        f"{started_at.isoformat()}|{finished_token}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def granularity_era(started_at: datetime, level: str) -> str:
    if started_at < GRANULARITY_ERA_CUTOFF and level == AdminLevel.OBLAST:
        return "oblast_dominant"
    if started_at >= GRANULARITY_ERA_CUTOFF and level in {AdminLevel.RAION, AdminLevel.HROMADA}:
        return "raion_dominant"
    return "mixed"


def map_vadimkin_row(row: pd.Series) -> dict:
    started_at = parse_utc_timestamp(str(row[VadimkinCol.STARTED_AT]))
    finished_raw = row[VadimkinCol.FINISHED_AT]
    finished_at = (
        parse_utc_timestamp(str(finished_raw))
        if pd.notna(finished_raw) and str(finished_raw).strip()
        else None
    )
    level = str(row[VadimkinCol.LEVEL])
    oblast = str(row[VadimkinCol.OBLAST])
    raion = str(row[VadimkinCol.RAION]) if pd.notna(row[VadimkinCol.RAION]) else ""
    hromada = str(row[VadimkinCol.HROMADA]) if pd.notna(row[VadimkinCol.HROMADA]) else ""

    return {
        EventCol.ALERT_ID: make_alert_id(oblast, raion, hromada, level, started_at, finished_at),
        EventCol.REGION_ID: None,
        EventCol.OBLAST: oblast,
        EventCol.RAION: raion,
        EventCol.HROMADA: hromada,
        EventCol.ADMIN_LEVEL: level,
        EventCol.STARTED_AT: started_at,
        EventCol.FINISHED_AT: finished_at,
        EventCol.GRANULARITY_ERA: granularity_era(started_at, level),
        EventCol.IS_OUTLIER_DURATION: is_outlier_duration(started_at, finished_at),
        EventCol.SOURCE: str(row[VadimkinCol.SOURCE]),
    }


def load_vadimkin_events(
    csv_path: str | pd.PathLike,
    *,
    region_id: str | None = None,
) -> pd.DataFrame:
    """Load raw CSV and return canonical event rows (one row per raw record)."""
    df = pd.read_csv(csv_path)
    if list(df.columns) != list(VADIMKIN_COLUMNS):
        raise ValueError(f"Unexpected Vadimkin header: {list(df.columns)}")

    if region_id is not None:
        spec = get_region(region_id)
        df = df.loc[df[VadimkinCol.OBLAST] == spec.vadimkin_oblast]

    records = [map_vadimkin_row(row) for _, row in df.iterrows()]
    return pd.DataFrame.from_records(records)
