"""Run exposure forecasts for a single forecast origin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from air_raid_alerts.config import display_timezone
from air_raid_alerts.models.exposure import model_prediction_column
from air_raid_alerts.models.persist import load_exposure_model
from air_raid_alerts.models.train import load_training_matrix
from air_raid_alerts.regions import get_region
from air_raid_alerts.schema import PanelCol


@dataclass(frozen=True)
class ExposureForecast:
    region_id: str
    region_name: str
    origin_hour_utc: datetime
    origin_hour_local: datetime
    probabilities: dict[int, float]


def parse_origin_hour(
    value: str | None,
    training_matrix: pd.DataFrame,
) -> pd.Timestamp:
    if value is None or value.lower() == "latest":
        return pd.Timestamp(training_matrix[PanelCol.ORIGIN_HOUR].max())

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.floor("h")


def forecast_row(
    training_matrix: pd.DataFrame,
    origin_hour: pd.Timestamp,
) -> pd.DataFrame:
    origins = pd.to_datetime(training_matrix[PanelCol.ORIGIN_HOUR], utc=True).dt.floor("h")
    matches = training_matrix.loc[origins == origin_hour]
    if matches.empty:
        raise ValueError(
            f"No processed row for origin hour {origin_hour.isoformat()}. "
            f"Run `air-alerts process` to refresh data."
        )
    if len(matches) > 1:
        raise ValueError(f"Multiple rows found for origin hour {origin_hour.isoformat()}")
    return matches


def predict_exposure_forecast(
    region_id: str,
    *,
    at: str | None = None,
    training_matrix_path: Path | None = None,
    model_path: Path | None = None,
) -> ExposureForecast:
    get_region(region_id)
    model = load_exposure_model(region_id, path=model_path)
    if model.region_id != region_id:
        raise ValueError(f"Model region {model.region_id!r} does not match requested {region_id!r}")

    training_matrix = load_training_matrix(region_id, csv_path=training_matrix_path)
    origin_hour = parse_origin_hour(at, training_matrix)
    row = forecast_row(training_matrix, origin_hour)
    predictions = model.predict(row)

    probabilities = {
        horizon: float(predictions.iloc[0][model_prediction_column(horizon)])
        for horizon in model.horizons
    }
    origin_utc = origin_hour.to_pydatetime()
    spec = get_region(region_id)
    return ExposureForecast(
        region_id=region_id,
        region_name=spec.display_name,
        origin_hour_utc=origin_utc,
        origin_hour_local=origin_utc.astimezone(display_timezone()),
        probabilities=probabilities,
    )


def format_forecast(forecast: ExposureForecast) -> str:
    local_time = forecast.origin_hour_local.strftime("%Y-%m-%d %H:%M %Z")
    utc_time = forecast.origin_hour_utc.strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"Region: {forecast.region_name} ({forecast.region_id})",
        f"Forecast origin: {local_time} ({utc_time})",
        "",
        "Horizon (hours)    P(under alert)",
    ]
    for horizon in sorted(forecast.probabilities):
        probability = forecast.probabilities[horizon]
        lines.append(f"{horizon:<18d} {probability:.2f}")
    return "\n".join(lines)
