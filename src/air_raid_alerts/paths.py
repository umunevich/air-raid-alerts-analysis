"""Project path helpers."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return repository root (directory containing pyproject.toml)."""
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Could not locate project root (pyproject.toml not found)")


def raw_vadimkin_dir() -> Path:
    return project_root() / "data" / "raw" / "vadimkin"


def processed_dir() -> Path:
    return project_root() / "data" / "processed"


def region_processed_dir(region_id: str) -> Path:
    return processed_dir() / region_id


def raw_vadimkin_csv() -> Path:
    return raw_vadimkin_dir() / "official_data_en.csv"


def raw_vadimkin_manifest() -> Path:
    return raw_vadimkin_dir() / "manifest.json"
