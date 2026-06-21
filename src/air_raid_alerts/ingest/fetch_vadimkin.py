"""Download Vadimkin official air-raid alert CSV into data/raw/."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from air_raid_alerts.paths import raw_vadimkin_dir

REPO = "Vadimkin/ukrainian-air-raid-sirens-dataset"
FILE_PATH = "datasets/official_data_en.csv"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"
API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"

EXPECTED_COLUMNS = (
    "oblast",
    "raion",
    "hromada",
    "level",
    "started_at",
    "finished_at",
    "source",
)
OUTPUT_FILENAME = "official_data_en.csv"
MANIFEST_FILENAME = "manifest.json"


def fetch_remote_metadata() -> dict:
    request = urllib.request.Request(
        API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "air-raid-alerts-analysis"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def load_manifest(manifest_path: Path) -> dict | None:
    if not manifest_path.is_file():
        return None
    with manifest_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def download_csv(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "air-raid-alerts-analysis"})

    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    ) as tmp:
        tmp_path = Path(tmp.name)
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    tmp.write(chunk)
            tmp_path.replace(destination)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise


def validate_csv(csv_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(EXPECTED_COLUMNS):
            expected = ", ".join(EXPECTED_COLUMNS)
            actual = ", ".join(reader.fieldnames or [])
            raise ValueError(
                f"Unexpected CSV header in {csv_path.name}.\n"
                f"Expected: {expected}\n"
                f"Got: {actual}"
            )
        return sum(1 for _ in reader)


def write_manifest(manifest_path: Path, payload: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def update_raw_data(output_dir: Path, *, force: bool = False) -> int:
    csv_path = output_dir / OUTPUT_FILENAME
    manifest_path = output_dir / MANIFEST_FILENAME

    print(f"Checking upstream metadata for {REPO} ...")
    remote = fetch_remote_metadata()
    remote_sha = remote["sha"]
    remote_size = remote["size"]

    local_manifest = load_manifest(manifest_path)
    if (
        not force
        and local_manifest
        and local_manifest.get("git_sha") == remote_sha
        and csv_path.is_file()
    ):
        print("Local copy is up to date (git sha unchanged).")
        print(f"  Path: {csv_path}")
        print(f"  Rows: {local_manifest.get('row_count', '?')}")
        print(f"  Updated at: {local_manifest.get('downloaded_at', '?')}")
        return 0

    print(f"Downloading {RAW_URL} ({remote_size:,} bytes) ...")
    download_csv(RAW_URL, csv_path)

    row_count = validate_csv(csv_path)
    downloaded_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    manifest = {
        "source": "vadimkin",
        "dataset": "official_data_en",
        "source_url": RAW_URL,
        "source_repo": f"https://github.com/{REPO}",
        "git_sha": remote_sha,
        "file_size_bytes": csv_path.stat().st_size,
        "row_count": row_count,
        "downloaded_at": downloaded_at,
        "columns": list(EXPECTED_COLUMNS),
    }
    write_manifest(manifest_path, manifest)

    print("Download complete.")
    print(f"  Path: {csv_path}")
    print(f"  Rows: {row_count:,}")
    print(f"  Manifest: {manifest_path}")
    return 0


def parse_fetch_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_dir = raw_vadimkin_dir()
    parser = argparse.ArgumentParser(
        description=(
            "Update local raw alert data from Vadimkin official_data_en.csv "
            "(Ukrainian air raid sirens dataset on GitHub)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_dir,
        help=f"Directory for CSV and manifest (default: {default_dir})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the upstream git sha has not changed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_fetch_args(argv)
    try:
        return update_raw_data(args.output_dir.resolve(), force=args.force)
    except urllib.error.HTTPError as exc:
        print(f"HTTP error {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error: {exc.reason}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1
