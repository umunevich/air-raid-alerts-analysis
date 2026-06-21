# air-raid-alerts-analysis

Time series analysis and probabilistic forecasting of Ukrainian air raid alerts.

## Problem

During an air war, people need a practical answer to a simple question:

> **Will my region be under an air raid alert at any point in the next N hours?**

This project builds hourly forecasts for that question. For a chosen region and forecast origin time `t`, it estimates **24 probabilities** — one for each horizon `N` from 1 to 24 hours.

The target is **exposure**, not “will a new alert start?”: if an alert is already active at `t` or begins during `(t, t+N]`, the label is positive. That matches the shelter-use case better than start-only prediction.

Features use only information available at or before `t`; labels describe the forward window `(t, t+N]`. Splits are **time-based** (train / validation / test), not random shuffles.

For the full problem definition, targets, baselines, and evaluation rules, see [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md). For data sources, interval construction, and per-region train windows, see [docs/DATA.md](docs/DATA.md).

## Setup

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `air-alerts` CLI and the `air_raid_alerts` Python package.

Configuration lives in `configs/default.yaml` (horizons, splits, default region, timezones, feature lags). Optional lag overrides: `configs/features.yaml`.

## Quick start

End-to-end workflow for the default region (`kyiv_city`):

```bash
# 1. Download raw alert history (Vadimkin official CSV)
air-alerts fetch

# 2. Build intervals, hourly labels, and feature matrix
air-alerts process --region kyiv_city

# 3. Train per-horizon logistic models, calibrate on validation, report test metrics
air-alerts train --region kyiv_city --write-metrics

# 4. Forecast probabilities for the latest available origin hour
air-alerts predict --region kyiv_city
```

### Outputs

After `process`, each region gets a folder under `data/processed/<region_id>/`:

| File | Description |
|------|-------------|
| `intervals.csv` | Merged alert intervals |
| `origins.csv` | Hourly panel with exposure labels `y_1` … `y_24` |
| `features.csv` | Feature matrix (no labels) |
| `training_matrix.csv` | Features + labels + split columns |
| `manifest.json` | Lineage and counts |

After `train`:

| File | Description |
|------|-------------|
| `exposure_model.joblib` | Fitted and calibrated model |
| `exposure_model_metrics.json` | Test metrics vs persistence and seasonal baselines (with `--write-metrics`) |

## Commands

| Command | Purpose |
|---------|---------|
| `air-alerts fetch` | Download `official_data_en.csv` into `data/raw/vadimkin/` |
| `air-alerts process --region REGION` | Clean raw data → intervals → hourly labels → features |
| `air-alerts train --region REGION` | Fit logistic models on primary train, calibrate on validation, score test |
| `air-alerts predict --region REGION` | Print 24 horizon probabilities for one origin hour |

Common options:

- **`--region`** — region ID from the registry (default: `kyiv_city`). Supported regions are listed in `configs/default.yaml`.
- **`--write-metrics`** (`train`) — save JSON metrics to the processed region directory.
- **`--at`** (`predict`) — forecast origin as UTC ISO-8601 timestamp or `latest` (default).
- **`--force`** (`fetch`) — re-download even if upstream data is unchanged.

Legacy script wrappers (optional):

```bash
python scripts/update_raw_data.py    # same as air-alerts fetch
python scripts/process_region.py --region kyiv_city
```

## Development

Run tests:

```bash
pytest
```

Lint:

```bash
ruff check src tests
```

## Project layout

```
configs/          YAML configuration
data/raw/         Downloaded Vadimkin CSV
data/processed/   Per-region artifacts
docs/             REQUIREMENTS.md, DATA.md
src/air_raid_alerts/
  ingest/         Raw data fetch
  transform/      Clean → intervals → panel → labels
  features/       Hourly feature matrix
  models/         Baselines, exposure model, train/predict
  evaluation/     Time splits and metrics
tests/
```

## Documentation

- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — prediction problem, target definition, baselines, metrics, MVP scope
- [docs/DATA.md](docs/DATA.md) — Vadimkin mapping, interval rules, train windows, QC checklist
