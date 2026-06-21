from pathlib import Path

from air_raid_alerts.paths import project_root, raw_vadimkin_dir


def test_project_root_contains_pyproject() -> None:
    root = project_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "docs" / "REQUIREMENTS.md").is_file()


def test_raw_vadimkin_dir_under_data() -> None:
    path = raw_vadimkin_dir()
    assert path.parts[-3:] == ("data", "raw", "vadimkin")
    assert path.is_relative_to(project_root())
