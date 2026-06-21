import csv
from pathlib import Path

import pytest

from air_raid_alerts.ingest.fetch_vadimkin import validate_csv
from air_raid_alerts.schema import VADIMKIN_COLUMNS, VadimkinCol


def test_validate_csv_accepts_expected_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(VADIMKIN_COLUMNS))
        writer.writeheader()
        writer.writerow(
            {
                VadimkinCol.OBLAST: "Kyiv City",
                VadimkinCol.RAION: "",
                VadimkinCol.HROMADA: "",
                VadimkinCol.LEVEL: "oblast",
                VadimkinCol.STARTED_AT: "2022-03-15 16:10:34+00:00",
                VadimkinCol.FINISHED_AT: "2022-03-15 16:50:07+00:00",
                VadimkinCol.SOURCE: "official",
            }
        )

    assert validate_csv(csv_path) == 1


def test_validate_csv_rejects_unexpected_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unexpected CSV header"):
        validate_csv(csv_path)
