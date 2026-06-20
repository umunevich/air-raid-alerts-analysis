# Project requirements

This document fixes the core prediction problem, target definitions, and scope for **air-raid-alerts-analysis**. Implementation details (models, libraries, data sources) may evolve; changes to this document should be deliberate and recorded.

---

## Primary question

> **Will a user-selected region be under an air raid alert at any time in the next N hours?**

The output is a **probability** (0–1), not a binary yes/no. The user chooses **one region**; the system does not predict nationwide or multi-region bundles in the MVP.

---

## Prediction specification

| Parameter | Value |
|-----------|--------|
| **Unit of prediction** | One region (oblast, city, or other stable ID from the alert feed) |
| **Forecast origin** | Every hour, on the hour |
| **Horizon N** | 1–24 hours (inclusive); produce one probability per N |
| **User-facing alert scope** | All alert types combined into a single probability |
| **Timezone (storage)** | UTC |
| **Timezone (display / features)** | `Europe/Kyiv` unless the region implies otherwise |

### Forecast origin timestamp

For origin time `t` (top of hour):

- **Features** may use information available at or before `t`.
- **Target** describes the interval `(t, t + N hours]` (open at `t`, closed at `t + N`).
- No feature may use alert or metadata timestamps **after** `t` (no leakage).

---

## Target definition

### User-facing target (what we evaluate and show)

Let `A_r(τ)` be 1 if region `r` is **under an active air raid alert** at instant `τ`, and 0 otherwise. An alert is active from `started_at` until `ended_at` (or until censored; see [Data requirements](#data-requirements)).

For forecast origin `t` and horizon `N`:

```
y_r,N(t) = 1  if  ∃ τ ∈ (t, t + N]  such that  A_r(τ) = 1
           0  otherwise
```

**Probability to predict:**

```
P_r,N(t) = P( y_r,N(t) = 1 | information available at t )
```

This is an **exposure** (occupancy) target: “will the region be under alert at some point in the window?”, not “will a new alert **start** in the window?”.

### Why exposure, not “new start”

Users care whether they will need to seek shelter during the next N hours. A long-running alert that started before `t` but is still active contributes to `y_r,N(t) = 1`. Start-only targets would understate risk during ongoing alerts.

---

## Alert types: internal vs user-facing

### User-facing (single number)

The UI and primary metrics report **one probability per (region, N)**:

> P(region under **any** configured alert type during the next N hours)

The user does not pick alert type in the MVP.

### Internal (type-aware modeling)

Alert types (e.g. air, drone, ballistic, artillery — exact enum follows the data source) are **tracked and modeled separately inside the pipeline**, then **aggregated** into the user-facing probability.

**Rationale:** Different types often have different timing, duration, and clustering. A single pooled model blurs those patterns; type-aware internals improve calibration while keeping the product simple.

**Recommended aggregation (default):**

For each alert type `k`, estimate type-conditional exposure probability `P_k` = P(region under type `k` at any time in `(t, t+N]` | info at `t`).

Combine with a **union** rule (at least one type active):

```
P_any ≈ 1 − ∏_k (1 − P_k)
```

Assumption: types are **approximately independent** for aggregation purposes. If the source encodes overlapping simultaneous alerts as one active state, prefer a **single latent “under alert”** label for training and use type only as **features** (see fallback below).

**Fallback if per-type labels are unreliable or sparse:**

- Train one binary model on `y_r,N(t)` (any type active).
- Enrich features with **type-specific history** (e.g. starts and active flags per type over the last 24–168 hours).
- Do not expose type-specific probabilities in the MVP UI.

**Decision rule for implementation:** Use per-type sub-targets when each type has enough history in the chosen region; otherwise use the fallback. Document the choice per region in `DATA.md` when known.

---

## Regions

- The user **selects exactly one region** per prediction context.
- Each region has a stable `region_id` aligned with the alert API or dataset.
- MVP: support a **small allowlist** of regions with sufficient history; expand later.
- Models may be **per-region** or **pooled with region as a feature**; the requirement is that inference accepts a user-picked `region_id` and returns probabilities for that region only.

---

## Horizons N = 1 … 24

- Emit **24 probabilities** per forecast origin: one for each `N ∈ {1, 2, …, 24}`.
- Horizons are **not independent** (nested windows: if under alert in the next hour, likely under alert in the next 24 hours). Models may:
  - train **separate calibrated models per N**, or
  - train a **multi-horizon** model with post-hoc monotonicity checks (optional, not required for MVP).
- **Evaluation** is reported **per N** (and aggregated summaries such as mean Brier across N are optional).

---

## Data requirements

### Required fields (per alert event)

| Field | Description |
|-------|-------------|
| `alert_id` | Stable identifier for deduplication |
| `region_id` | Region the alert applies to |
| `alert_type` | Type enum from source (mapped to internal canonical types) |
| `started_at` | When the alert became active (UTC) |
| `ended_at` | When the alert cleared (UTC); nullable if still open at ingest time |

### Derived series (hourly, per region)

At each hour `t` and region `r`:

- `active_any(r, t)` — 1 if any alert type is active during that hour (or at hour boundary; define consistently in code).
- `active_k(r, t)` — same, per type `k`.
- Optional: minutes under alert within the hour, time since last start/end, type-specific lags.

### Label construction

From `active_*` and event intervals, build `y_r,N(t)` for all `N ∈ 1..24` using the exposure definition above. Unit tests must assert **no future information** in features at `t`.

### Data quality

- Deduplicate repeated records for the same `alert_id`.
- Normalize timezones to UTC at ingest.
- Map raw alert types to a **canonical internal enum**; document mapping in `DATA.md`.
- **Censoring:** alerts without `ended_at` at dataset cutoff — document handling (e.g. exclude open-ended intervals from duration stats; treat as active until ingest time for label construction, with a noted bias).

### Minimum data (guideline)

- Per supported region: enough hourly origins to estimate rare events (target: **≥ 6 months** of history where possible).
- Sufficient **positive** origins (`y_r,N(t) = 1`) for stable validation; quiet regions may need pooling or wider geographic units later.

---

## Modeling and evaluation (requirements-level)

### Baselines (must beat to claim success)

1. **Marginal rate:** historical fraction of origins with `y_r,N(t) = 1`.
2. **Seasonal baseline:** same, stratified by hour-of-week (and optionally type-specific activity).
3. **Persistence:** if `active_any(r, t) = 1`, predict high `P` for short N; else low.

### Primary models (implementation choice)

- Type-aware internal models + union aggregation (preferred when data supports it), **or** single binary model with type-aware features (fallback).
- Probabilities must be **calibrated** on a held-out time period (not random split).

### Train / validation / test split

- **Time-based only** — e.g. train on older months, validate for calibration and threshold tuning, test on the most recent held-out period.
- No random shuffling of hours across time.

### Metrics (per region and per N)

| Metric | Role |
|--------|------|
| **Brier score** | Primary proper scoring rule |
| **Log loss** | Penalize overconfident errors |
| **PR-AUC** | Important when positives are rare |
| **Calibration (ECE / reliability curves)** | “When we say 20%, it happens ~20%” |
| **Baseline uplift** | Report improvement over seasonal baseline |

Optional: tune a **decision threshold** on validation for a fixed false-alarm rate; default scoring uses probabilistic metrics, not accuracy at 0.5.

---

## User-facing output (MVP)

For chosen `region_id` and origin hour `t`:

```text
Horizon (hours)    P(under alert)
1                  0.12
2                  0.18
…
24                 0.67
```

- Single column of probabilities (all types combined).
- Optionally show **forecast origin time** and **region name** in local time.
- Do **not** require alert-type selection in the MVP.

---

## Out of scope (MVP)

- Real-time streaming ingestion and push notifications
- Multi-region simultaneous forecast in one request
- Exposing per-type probabilities in the UI
- Start-time-only prediction (“will a **new** alert begin?”) as the primary product metric
- Causal claims about external drivers (weather, news, etc.)

These may be added in later phases if requirements are updated here.

---

## Glossary

| Term | Meaning |
|------|---------|
| **Forecast origin** | Hour `t` at which the forecast is issued; features use data ≤ `t`. |
| **Horizon N** | Length of the forward window `(t, t+N]` in hours. |
| **Exposure / under alert** | Region has at least one active alert at some moment in the window. |
| **Alert type** | Canonical category from the feed; used internally for modeling. |
| **User-facing probability** | `P_any` — union over types, one number per N. |

---

## Document history

| Date | Change |
|------|--------|
| 2026-06-20 | Initial requirements: region-specific exposure probability, hourly origins, N=1–24, type-aware internal / unified external. |
