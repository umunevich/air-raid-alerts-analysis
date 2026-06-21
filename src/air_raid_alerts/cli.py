"""Command-line interface."""

from __future__ import annotations

import argparse
import sys

from air_raid_alerts import __version__
from air_raid_alerts.config import default_region_id
from air_raid_alerts.ingest.fetch_vadimkin import main as fetch_main
from air_raid_alerts.models.persist import model_output_path
from air_raid_alerts.models.predict import format_forecast, predict_exposure_forecast
from air_raid_alerts.models.train import format_report, metrics_output_path, train_and_evaluate, write_report_json
from air_raid_alerts.transform.pipeline import process_region


def _default_region() -> str:
    return default_region_id()


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
        default=_default_region(),
        help=f"Region ID from registry (default: {default_region_id()}).",
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

    train_parser = subparsers.add_parser(
        "train",
        help="Train per-horizon logistic exposure models and report test metrics.",
    )
    train_parser.add_argument(
        "--region",
        default=_default_region(),
        help=f"Region ID from registry (default: {default_region_id()}).",
    )
    train_parser.add_argument(
        "--training-matrix",
        type=str,
        default=None,
        help="Override path to training_matrix.csv.",
    )
    train_parser.add_argument(
        "--write-metrics",
        action="store_true",
        help="Write exposure_model_metrics.json to the processed region directory.",
    )

    predict_parser = subparsers.add_parser(
        "predict",
        help="Forecast exposure probabilities for one origin hour.",
    )
    predict_parser.add_argument(
        "--region",
        default=_default_region(),
        help=f"Region ID from registry (default: {default_region_id()}).",
    )
    predict_parser.add_argument(
        "--at",
        default="latest",
        help="Forecast origin hour (UTC ISO-8601) or 'latest' (default: latest).",
    )
    predict_parser.add_argument(
        "--training-matrix",
        type=str,
        default=None,
        help="Override path to training_matrix.csv.",
    )
    predict_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override path to exposure_model.joblib.",
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

    if args.command == "train":
        from pathlib import Path

        try:
            _model, report = train_and_evaluate(
                args.region,
                csv_path=Path(args.training_matrix) if args.training_matrix else None,
            )
        except (FileNotFoundError, ValueError, KeyError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        print(format_report(report))
        if args.write_metrics:
            metrics_path = metrics_output_path(args.region)
            write_report_json(report, metrics_path)
            print(f"\nMetrics written to {metrics_path}")
        print(f"Model saved to {model_output_path(args.region)}")
        return 0

    if args.command == "predict":
        from pathlib import Path

        try:
            forecast = predict_exposure_forecast(
                args.region,
                at=args.at,
                training_matrix_path=Path(args.training_matrix) if args.training_matrix else None,
                model_path=Path(args.model) if args.model else None,
            )
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        print(format_forecast(forecast))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
