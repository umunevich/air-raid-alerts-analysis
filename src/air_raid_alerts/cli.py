"""Command-line interface."""

from __future__ import annotations

import argparse
import sys

from air_raid_alerts import __version__
from air_raid_alerts.ingest.fetch_vadimkin import main as fetch_main
from air_raid_alerts.transform.pipeline import process_region


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="air-alerts",
        description="Air raid alert time series analysis and forecasting.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Download Vadimkin official_data_en.csv into data/raw/vadimkin/",
    )
    fetch_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory (default: data/raw/vadimkin/)",
    )
    fetch_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if upstream git sha is unchanged.",
    )

    process_parser = subparsers.add_parser(
        "process",
        help="Build processed intervals and hourly origins for one region.",
    )
    process_parser.add_argument(
        "--region",
        default="kyiv_city",
        help="Region ID from registry (default: kyiv_city).",
    )
    process_parser.add_argument(
        "--raw-csv",
        type=str,
        default=None,
        help="Override path to Vadimkin official_data_en.csv.",
    )
    process_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory (default: data/processed/<region>/).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)

    if args.command == "fetch":
        fetch_argv: list[str] = []
        if args.output_dir:
            fetch_argv.extend(["--output-dir", args.output_dir])
        if args.force:
            fetch_argv.append("--force")
        fetch_argv.extend(extra)
        return fetch_main(fetch_argv)

    if args.command == "process":
        try:
            result = process_region(
                args.region,
                raw_csv_path=args.raw_csv,
                output_dir=args.output_dir,
            )
        except (FileNotFoundError, ValueError, KeyError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        print("Processing complete.")
        print(f"  Region: {result.region_id}")
        print(f"  Output: {result.output_dir}")
        print(f"  Intervals: {len(result.intervals):,}")
        print(f"  Origins: {len(result.origins):,}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
