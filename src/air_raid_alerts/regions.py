"""Region registry and slug helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

RollupMode = Literal["none", "oblast"]


@dataclass(frozen=True)
class RegionSpec:
    region_id: str
    display_name: str
    vadimkin_oblast: str
    rollup: RollupMode
    excluded: bool = False
    primary_train_months: int | None = None


REGION_REGISTRY: dict[str, RegionSpec] = {
    "kyiv_city": RegionSpec(
        region_id="kyiv_city",
        display_name="Kyiv City",
        vadimkin_oblast="Kyiv City",
        rollup="none",
        primary_train_months=18,
    ),
    "kyivska_oblast": RegionSpec(
        region_id="kyivska_oblast",
        display_name="Kyivska oblast",
        vadimkin_oblast="Kyivska oblast",
        rollup="oblast",
        primary_train_months=12,
    ),
    "kharkivska_oblast": RegionSpec(
        region_id="kharkivska_oblast",
        display_name="Kharkivska oblast",
        vadimkin_oblast="Kharkivska oblast",
        rollup="oblast",
        primary_train_months=12,
    ),
    "lvivska_oblast": RegionSpec(
        region_id="lvivska_oblast",
        display_name="Lvivska oblast",
        vadimkin_oblast="Lvivska oblast",
        rollup="oblast",
        primary_train_months=24,
    ),
    "dnipropetrovska_oblast": RegionSpec(
        region_id="dnipropetrovska_oblast",
        display_name="Dnipropetrovska oblast",
        vadimkin_oblast="Dnipropetrovska oblast",
        rollup="oblast",
        primary_train_months=12,
    ),
    "odeska_oblast": RegionSpec(
        region_id="odeska_oblast",
        display_name="Odeska oblast",
        vadimkin_oblast="Odeska oblast",
        rollup="oblast",
        primary_train_months=18,
    ),
    "sumska_oblast": RegionSpec(
        region_id="sumska_oblast",
        display_name="Sumska oblast",
        vadimkin_oblast="Sumska oblast",
        rollup="oblast",
        primary_train_months=12,
    ),
    "luhanska_oblast": RegionSpec(
        region_id="luhanska_oblast",
        display_name="Luhanska oblast",
        vadimkin_oblast="Luhanska oblast",
        rollup="oblast",
        excluded=True,
    ),
}


def slugify(name: str) -> str:
    """Normalize a display name to a region_id slug."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower())
    return slug.strip("_")


def get_region(region_id: str) -> RegionSpec:
    if region_id not in REGION_REGISTRY:
        raise KeyError(f"Unknown region_id: {region_id}")
    spec = REGION_REGISTRY[region_id]
    if spec.excluded:
        raise ValueError(f"Region {region_id} is excluded from MVP")
    return spec


def list_allowlisted_regions() -> list[str]:
    return [rid for rid, spec in REGION_REGISTRY.items() if not spec.excluded]
