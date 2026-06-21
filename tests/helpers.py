"""Shared helpers for pipeline tests (importable without package prefix)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from air_raid_alerts.schema import IntervalCol, VADIMKIN_COLUMNS

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def sample_vadimkin_path() -> Path:
    return FIXTURES_DIR / "sample_vadimkin.csv"


def sample_manifest_path() -> Path:
    return FIXTURES_DIR / "manifest.json"


def vadimkin_columns_json() -> list[str]:
    return list(VADIMKIN_COLUMNS)


def intervals_df(
    region_id: str,
    pairs: list[tuple[datetime, datetime]],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            IntervalCol.REGION_ID: region_id,
            IntervalCol.STARTED_AT: [p[0] for p in pairs],
            IntervalCol.FINISHED_AT: [p[1] for p in pairs],
            IntervalCol.IS_OUTLIER_DURATION: [False] * len(pairs),
        }
    )
