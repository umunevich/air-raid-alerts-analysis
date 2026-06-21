# Data specification

This document describes data sources, field mappings, interval construction, and recommended training windows per region. It complements [REQUIREMENTS.md](./REQUIREMENTS.md).

**MVP scope:** type-agnostic alerts only (Vadimkin official CSV). Alert-type enrichment is [deferred](#future-alert-types).

For raw ingest, run:

```bash
python3 scripts/update_raw_data.py
```

Raw files live under `data/raw/vadimkin/` with metadata in `manifest.json`.

---

## Data sources


| Role        | Source                          | Location / access    | Used for                                                         |
| ----------- | ------------------------------- | -------------------- | ---------------------------------------------------------------- |
| **Primary** | Vadimkin `official_data_en.csv` | `data/raw/vadimkin/` | `started_at` / `finished_at`, hourly `active`, labels `y_r,N(t)` |


**Do not mix** Vadimkin `volunteer_data_*.csv` into the official pipeline without a separate harmonization spec (different start date, imputed ends, oblast-only).

### Future sources (not in MVP)

When alert types are added later, secondary sources may include [alerts.in.ua](https://devs.alerts.in.ua/), [Kyiv open data](https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal), and live collectors. See [Future: alert types](#future-alert-types).

---

## Canonical event schema

Target schema after cleaning (one row per logical interval **after merge**, before hourly aggregation):


| Field                 | Type           | Description                                                    |
| --------------------- | -------------- | -------------------------------------------------------------- |
| `alert_id`            | string         | Synthetic stable ID (see below)                                |
| `region_id`           | string         | Canonical region key (see [Region registry](#region-registry)) |
| `started_at`          | datetime (UTC) | Alert became active                                            |
| `finished_at`         | datetime (UTC) | Alert cleared; nullable if censored at ingest cutoff           |
| `admin_level`         | enum           | `oblast` | `raion` | `hromada` | `city`                        |
| `granularity_era`     | string         | `oblast_dominant` | `raion_dominant` | `mixed`                 |
| `is_outlier_duration` | bool           | True if duration exceeds QC threshold                          |


---

## Vadimkin → canonical mapping

Direct column mapping (no rename required):


| Vadimkin      | Canonical           | Notes                                 |
| ------------- | ------------------- | ------------------------------------- |
| `oblast`      | part of `region_id` | English names; see registry           |
| `raion`       | part of `region_id` | Empty when `level=oblast`             |
| `hromada`     | part of `region_id` | Empty when `level` is oblast or raion |
| `level`       | `admin_level`       | `oblast`, `raion`, or `hromada`       |
| `started_at`  | `started_at`        | Already UTC                           |
| `finished_at` | `finished_at`       | Already UTC                           |
| `source`      | lineage only        | Always `official` in this file        |
| —             | `alert_id`          | **Generated**                         |


### Synthetic `alert_id`

```text
alert_id = sha256("{oblast}|{raion}|{hromada}|{level}|{started_at}|{finished_at}")[:16]
```

Use for deduplication within a processed snapshot. Not an official government ID.

### Granularity era (Vadimkin official)

Policy shifted toward **raion-level** alerts around **December 2025**. Tag each row from `started_at`:


| Condition                                                         | `granularity_era` |
| ----------------------------------------------------------------- | ----------------- |
| `started_at` < 2025-12-01 and row `level=oblast`                  | `oblast_dominant` |
| `started_at` ≥ 2025-12-01 and row `level` in (`raion`, `hromada`) | `raion_dominant`  |
| Otherwise                                                         | `mixed`           |


When forecasting for a **whole oblast**, roll up all sub-units (see [Interval construction](#interval-construction)); do not rely on sparse oblast-level rows alone after 2025.

---

## Region registry

Stable `region_id` slugs for MVP allowlist. Display names are user-facing.


| `region_id`              | Display name           | Vadimkin filter                      | Forecast unit                  | MVP status                                |
| ------------------------ | ---------------------- | ------------------------------------ | ------------------------------ | ----------------------------------------- |
| `kyiv_city`              | Kyiv City              | `oblast == "Kyiv City"`              | City (all rows `level=oblast`) | **Recommended MVP**                       |
| `kyivska_oblast`         | Kyivska oblast         | `oblast == "Kyivska oblast"`         | Whole oblast (rollup)          | Supported; harder post-2025               |
| `kharkivska_oblast`      | Kharkivska oblast      | `oblast == "Kharkivska oblast"`      | Whole oblast (rollup)          | Supported                                 |
| `lvivska_oblast`         | Lvivska oblast         | `oblast == "Lvivska oblast"`         | Whole oblast (rollup)          | Supported; quieter                        |
| `dnipropetrovska_oblast` | Dnipropetrovska oblast | `oblast == "Dnipropetrovska oblast"` | Whole oblast (rollup)          | Supported                                 |
| `odeska_oblast`          | Odeska oblast          | `oblast == "Odeska oblast"`          | Whole oblast (rollup)          | Supported                                 |
| `sumska_oblast`          | Sumska oblast          | `oblast == "Sumska oblast"`          | Whole oblast (rollup)          | Supported                                 |
| `luhanska_oblast`        | Luhanska oblast        | —                                    | —                              | **Excluded** (2 rows; occupied territory) |


**Kyiv City ≠ Kyivska oblast.** Users must pick explicitly; models and data paths are not interchangeable.

Raion- or hromada-level forecasting (user picks a sub-unit) uses the same slug pattern:

```text
{oblast_slug}/{raion_slug}   e.g. kharkivska_oblast/kharkivskyi_raion
```

Normalize slugs: lowercase, ASCII, spaces → underscores, strip punctuation.

---

## Interval construction

Raw Vadimkin rows are **not** one row per user-visible alert. One event often appears as many rows (same `oblast` + `started_at`, different raions). Pipeline order:

1. **Filter** to target `region_id` (and sub-units if raion/hromada forecast).
2. **Roll up** (whole-oblast forecasts only): at each instant, region is active if **any** filtered row is active.
3. **Merge** overlapping intervals `[started_at, finished_at]` into disjoint merged intervals.
4. **QC flag** `is_outlier_duration` if duration > **7 days** (review; file contains rare multi-month spans, likely bad end times).

Interval boundary convention (must match label code):

- Alert active for all `τ` with `started_at ≤ τ ≤ finished_at` (inclusive end), unless changed in code — document in tests.
- Hourly `active(r, t)`: 1 if any active instant falls in hour `(t, t+1h]` or `[t, t+1h)` — pick one; default `**[t, t+1h)`** (hour starting at origin).

---

## Train / validation / test splits

**Always time-based** on hourly forecast origins. Never shuffle rows or hours across time.

Default split template (adjust dates when running; anchor to `data_cutoff` = last `finished_at` in manifest):


| Split          | Default window                                               | Purpose                             |
| -------------- | ------------------------------------------------------------ | ----------------------------------- |
| **Train**      | See [per-region table](#recommended-train-window-per-region) | Fit models                          |
| **Validation** | 8 weeks immediately before test                              | Calibration, threshold tuning       |
| **Test**       | Most recent 4 weeks                                          | Report Brier, log loss, PR-AUC, ECE |


Example if `data_cutoff = 2026-06-20`:

- Test: `2026-05-23` → `2026-06-20`
- Val: `2026-03-28` → `2026-05-23`
- Train: per region, ends at `2026-03-28`

Optional **pretrain** pool: older Vadimkin history before primary train window with **sample weight 0.25–0.5** for the exposure model only.

---

## Recommended train window per region

Based on Vadimkin `official_data_en.csv` snapshot (`git_sha` in `data/raw/vadimkin/manifest.json`, **271,160** rows, **2022-03-15** → **2026-06-20**).

Columns:

- **Primary train** — main supervised fit for 2026-facing forecasts
- **Baseline / seasonality** — optional longer window for marginal and hour-of-week baselines only
- **Notes** — region-specific caveats


| `region_id`              | Interval rows (raw) | Primary train                                 | Baseline / seasonality                          | Notes                                                              |
| ------------------------ | ------------------- | --------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| `kyiv_city`              | 3,951               | **Last 18 months** (`2024-12-20` → val start) | Full history from `2022-03-15`                  | Single admin level; **best MVP**                                   |
| `kyivska_oblast`         | 9,615               | **Last 12 months** with **raion rollup**      | `2023-01-01` → primary start for baselines only | Post-2025: **5,539** raion vs **926** oblast rows; rollup required |
| `kharkivska_oblast`      | 35,034              | **Last 12–18 months**                         | Full history from `2022-03-15`                  | High activity; watch long-duration QC outliers                     |
| `lvivska_oblast`         | 2,296               | **Last 24 months**                            | Full history                                    | Quieter; needs longer window for positive `y_r,N`                  |
| `dnipropetrovska_oblast` | 41,990              | **Last 12 months**                            | `2022-03-15` → baselines                        | Very high volume; heavy hromada/raion mix in 2025+                 |
| `odeska_oblast`          | 10,772              | **Last 18 months**                            | Full history                                    | Moderate volume; raion-heavy in 2025+                              |
| `sumska_oblast`          | 18,787              | **Last 12 months**                            | Full history                                    | Border oblast; raion-dominant in 2025+                             |
| `luhanska_oblast`        | 2                   | —                                             | —                                               | **Do not train**                                                   |


### How to apply per region

1. **Labels** (`y_r,N`): build from full available Vadimkin history after merge/rollup; slice origins by split dates above.
2. **Primary model fit:** use only **primary train** rows (recent-heavy).
3. **Seasonal baseline:** compute on **baseline / seasonality** window (can include all history).
4. **Report metrics** on **test**; optionally report second test on pre-Dec-2025 era to show granularity shift impact.

### Why not all history for training?

- Alert policy (**oblast → raion**) changed ~Dec 2025.
- Conflict intensity and timing patterns evolved (2024–2026 ≠ 2022).

Older data helps **baselines and seasonality**; recent data drives **calibrated forecasts** for current conditions.

---

## Future: alert types

Not implemented in MVP. When added, update [REQUIREMENTS.md](./REQUIREMENTS.md) first, then extend this section.

**Likely approach:**

1. **Sources:** alerts.in.ua API (nationwide), Kyiv open data (city), hourly collector for forward data.
2. **Schema additions:** `alert_type`, optional `alert_types`, `type_source`, `type_match_confidence`, `type_match_method`.
3. **Join strategy:** interval overlap onto Vadimkin merged intervals; labels stay on Vadimkin exposure spine.
4. **Modeling:** per-type internal features or sub-models; user-facing probability remains a single `P_r,N(t)` unless requirements change.
5. **Config files (planned):** `configs/region_crosswalk.csv`, `configs/alert_type_mapping.yaml`.

**Draft canonical enum** (for reference only):


| Canonical       | Description                      |
| --------------- | -------------------------------- |
| `air_raid`      | General air raid / shelter alert |
| `artillery`     | Artillery / shelling             |
| `drone`         | UAV / Shahed-type threat         |
| `missile`       | Missile / ballistic threat       |
| `urban_warfare` | Ground / urban combat risk       |


---

## Exclusions and special cases


| Case                                           | Handling                                                  |
| ---------------------------------------------- | --------------------------------------------------------- |
| **Luhanska oblast**                            | Exclude from MVP allowlist (2 rows in official snapshot). |
| **Crimea / permanent occupied alerts**         | Not represented in Vadimkin official CSV; do not impute.  |
| **Volunteer CSV**                              | Separate dataset; not part of this pipeline.              |
| **Duplicate rows same `(oblast, started_at)`** | Resolve via rollup + merge, not row dedupe alone.         |
| **Zero-length / sub-minute intervals**         | Keep for exposure; flag in QC stats.                      |
| **Open `finished_at` at future cutoff**        | Treat as active until ingest time; mark censored.         |


---

## Data quality checks (minimum)

Run after each raw update and after transform:

- [ ] CSV header matches manifest `columns`
- [ ] Row count within ~1% of manifest (or manifest refreshed)
- [ ] No `finished_at < started_at`
- [ ] For each MVP `region_id`: merged interval count and hourly positive rate documented
- [ ] Leakage test: no feature at origin `t` uses timestamps after `t`

---

## Document history


| Date       | Change                                                                              |
| ---------- | ----------------------------------------------------------------------------------- |
| 2026-06-20 | Initial DATA.md: Vadimkin mapping, type join rules, per-region train windows.       |
| 2026-06-20 | Defer alert types; MVP uses Vadimkin only; type enrichment moved to Future section. |


