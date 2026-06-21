# air-raid-alerts-analysis

Time series analysis and probabilistic forecasting of air raid alerts in Ukraine.

See [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) and [docs/DATA.md](docs/DATA.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Or install dependencies only:

```bash
pip install -r requirements-dev.txt
```

## Update raw data

```bash
python scripts/update_raw_data.py
# or
air-alerts fetch
```

## Build processed data (Kyiv city)

```bash
air-alerts process --region kyiv_city
# or
python scripts/process_region.py --region kyiv_city
```

Writes `data/processed/kyiv_city/intervals.csv`, `origins.csv`, and `manifest.json`.
