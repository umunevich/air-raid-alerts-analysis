"""Load project configuration from configs/default.yaml (and optional features overrides)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from air_raid_alerts.paths import project_root

DEFAULT_CONFIG_PATH = project_root() / "configs" / "default.yaml"
FEATURES_CONFIG_PATH = project_root() / "configs" / "features.yaml"

DEFAULT_TIMEZONE_STORE = "UTC"
DEFAULT_TIMEZONE_DISPLAY = "Europe/Kyiv"
DEFAULT_RESOLUTION = "1h"
DEFAULT_REGION_ID = "kyiv_city"
DEFAULT_FORECAST_HORIZONS: tuple[int, ...] = tuple(range(1, 25))
DEFAULT_FEATURE_LAG_HOURS: tuple[int, ...] = (1, 3, 6, 24, 48, 168)
DEFAULT_VALIDATION_WEEKS = 8
DEFAULT_TEST_WEEKS = 4


@dataclass(frozen=True)
class AppConfig:
    timezone_store: str
    timezone_display: str
    resolution: str
    forecast_horizons: tuple[int, ...]
    default_region_id: str
    region_allowlist: tuple[str, ...]
    validation_weeks: int
    test_weeks: int
    feature_lag_hours: tuple[int, ...]

    @property
    def display_timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_display)


def _as_int_tuple(values: object, *, fallback: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(values, list):
        return fallback
    return tuple(int(value) for value in values)


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def load_app_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    raw = _load_yaml(config_path) if config_path.is_file() else {}

    project = raw.get("project", {})
    forecast = raw.get("forecast", {})
    regions = raw.get("regions", {})
    splits = raw.get("splits", {})
    features = raw.get("features", {})

    lag_hours = _as_int_tuple(
        features.get("lags_hours"),
        fallback=DEFAULT_FEATURE_LAG_HOURS,
    )

    if FEATURES_CONFIG_PATH.is_file():
        feature_overrides = _load_yaml(FEATURES_CONFIG_PATH)
        lag_hours = _as_int_tuple(
            feature_overrides.get("lags_hours"),
            fallback=lag_hours,
        )

    allowlist = regions.get("allowlist", [])
    if not isinstance(allowlist, list):
        allowlist = []

    return AppConfig(
        timezone_store=str(project.get("timezone_store", DEFAULT_TIMEZONE_STORE)),
        timezone_display=str(project.get("timezone_display", DEFAULT_TIMEZONE_DISPLAY)),
        resolution=str(project.get("resolution", DEFAULT_RESOLUTION)),
        forecast_horizons=_as_int_tuple(
            forecast.get("horizons_hours"),
            fallback=DEFAULT_FORECAST_HORIZONS,
        ),
        default_region_id=str(regions.get("default", DEFAULT_REGION_ID)),
        region_allowlist=tuple(str(region_id) for region_id in allowlist),
        validation_weeks=int(splits.get("validation_weeks", DEFAULT_VALIDATION_WEEKS)),
        test_weeks=int(splits.get("test_weeks", DEFAULT_TEST_WEEKS)),
        feature_lag_hours=lag_hours,
    )


def default_forecast_horizons() -> tuple[int, ...]:
    return load_app_config().forecast_horizons


def default_region_id() -> str:
    return load_app_config().default_region_id


def default_split_weeks() -> tuple[int, int]:
    config = load_app_config()
    return config.validation_weeks, config.test_weeks


def default_feature_lag_hours() -> tuple[int, ...]:
    return load_app_config().feature_lag_hours


def display_timezone() -> ZoneInfo:
    return load_app_config().display_timezone
