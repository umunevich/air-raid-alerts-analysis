"""Pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import sample_manifest_path as get_sample_manifest_path
from helpers import sample_vadimkin_path as get_sample_vadimkin_path


@pytest.fixture
def sample_vadimkin_path() -> Path:
    return get_sample_vadimkin_path()


@pytest.fixture
def sample_manifest_path() -> Path:
    return get_sample_manifest_path()
