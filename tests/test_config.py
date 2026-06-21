"""Tests for application configuration loading."""

from air_raid_alerts.config import (
    DEFAULT_REGION_ID,
    DEFAULT_TEST_WEEKS,
    DEFAULT_VALIDATION_WEEKS,
    load_app_config,
)
from air_raid_alerts.schema import SplitName


def test_load_app_config_reads_default_yaml() -> None:
    config = load_app_config()
    assert config.default_region_id == DEFAULT_REGION_ID
    assert config.timezone_display == "Europe/Kyiv"
    assert config.validation_weeks == DEFAULT_VALIDATION_WEEKS
    assert config.test_weeks == DEFAULT_TEST_WEEKS
    assert config.forecast_horizons == tuple(range(1, 25))
    assert config.feature_lag_hours == (1, 3, 6, 24, 48, 168)


def test_split_name_constants() -> None:
    assert SplitName.TRAIN == "train"
    assert SplitName.VALIDATION == "validation"
    assert SplitName.TEST == "test"
    assert SplitName.HOLDOUT == "holdout"
