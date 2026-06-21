"""Tests for region registry."""

import pytest

from air_raid_alerts.regions import get_region, list_allowlisted_regions, slugify


def test_slugify_normalizes_names() -> None:
    assert slugify("Kyiv City") == "kyiv_city"
    assert slugify("Kharkivska oblast") == "kharkivska_oblast"


def test_list_allowlisted_regions_excludes_luhansk() -> None:
    regions = list_allowlisted_regions()
    assert "kyiv_city" in regions
    assert "luhanska_oblast" not in regions


def test_get_region_kyiv_city() -> None:
    spec = get_region("kyiv_city")
    assert spec.vadimkin_oblast == "Kyiv City"
    assert spec.rollup == "none"


def test_get_region_raises_for_excluded() -> None:
    with pytest.raises(ValueError, match="excluded"):
        get_region("luhanska_oblast")


def test_get_region_raises_for_unknown() -> None:
    with pytest.raises(KeyError):
        get_region("not_a_region")
