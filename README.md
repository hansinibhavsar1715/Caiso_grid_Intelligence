# ⚡ CAISO Grid Stress & Electricity Price Intelligence Pipeline

An end-to-end data pipeline that ingests real-time electricity demand and price data from two independent APIs, validates and stores it, engineers time-series features, forecasts next-hour price and grid stress using machine learning, and surfaces everything on a live Streamlit dashboard.

**Live pipeline runs hourly, fully unattended, via Windows Task Scheduler.**

---

## 📌 Project Overview

Power grids operate on a tight balance between supply and demand. When demand nears capacity — due to heatwaves, generation outages, or high renewable variability — prices spike and reliability risk rises. Grid operators and government agencies publish this data publicly, but almost no public data-analyst portfolio project actually uses it in real time.

This project builds a production-style pipeline around **CAISO** (California's grid operator), combining:
- **U.S. Energy Information Administration (EIA)** — hourly demand, generation, and interchange data
- **GridStatus.io** — real-time 5-minute locational marginal price (LMP) data across major CAISO trading hubs

The goal: demonstrate a complete, realistic data analyst workflow — API integration, automation, SQL design, data validation, feature engineering, forecasting, and dashboarding — on genuinely live, messy, real-world data rather than a static Kaggle CSV.

---

## 🎯 Objective

Build an automated system that:
1. Continuously ingests near-real-time grid demand and price data
2. Validates data quality and handles source-specific reporting lag gracefully
3. Stores data in a properly normalized SQL schema
4. Forecasts next-hour electricity price and a custom "grid stress" index
5. Visualizes live conditions and forecasts on an interactive dashboard

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   EIA API   │     │  GridStatus.io   │     │                  │
│  (demand)   │     │     (price)      │     │                  │
└──────┬──────┘     └────────┬─────────┘     │   Runs hourly    │
       │                     │               │   via Windows    │
       ▼                     ▼               │  Task Scheduler  │
┌─────────────────────────────────────┐      │                  │
│         ingestion (Python)          │◄─────┘                  │
│   fetch → save raw CSV → load SQL   │
└──────────────────┬───────────────────┘
                    ▼
┌─────────────────────────────────────┐
│         SQLite Database             │
│  raw_eia | raw_gridstatus (audit)   │
│  fact_grid_hourly (clean, joined)   │
└──────────────────┬───────────────────┘
                    ▼
┌─────────────────────────────────────┐
│      Validation & Transform         │
│  quality checks → pivot → resample  │
│         → join → dedupe             │
└──────────────────┬───────────────────┘
                    ▼
┌─────────────────────────────────────┐
│      Feature Engineering            │
│  lags, rolling stats, calendar,     │
│  forecast-error, stress index       │
└──────────────────┬───────────────────┘
                    ▼
┌─────────────────────────────────────┐
│   ML Forecasting (HistGradient      │
│         Boosting Regressor)         │
│  next-hour price | stress score     │
└──────────────────┬───────────────────┘
                    ▼
┌─────────────────────────────────────┐
│      Streamlit Dashboard            │
│  live metrics, forecasts, charts    │
└──────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Category | Tools |
|---|---|
| Language | Python 3.10 |
| APIs | EIA API v2, GridStatus.io API |
| Database | SQLite |
| Data processing | pandas, NumPy |
| Machine learning | scikit-learn (HistGradientBoostingRegressor) |
| Dashboard | Streamlit, Plotly |
| Automation | Windows Task Scheduler |
| Environment management | python-dotenv |

---

## 📂 Project Structure

```
EIA ERCOT PROJECT/
├── .env                      # API keys (not committed)
├── .gitignore
├── app.py                    # Streamlit dashboard
├── ingest/
│   ├── __init__.py
│   ├── eia_fetch.py          # EIA API client
│   ├── gridstatus_fetch.py   # GridStatus.io API client
│   ├── save_raw.py           # Timestamped raw CSV audit trail
│   ├── db.py                 # SQLite schema definition
│   ├── load_to_db.py         # CSV → SQL loader with dedup
│   ├── validate.py           # Data quality checks
│   ├── transform.py          # Pivot, resample, join → fact table
│   ├── features.py           # Feature engineering
│   ├── train_model.py        # Model training & evaluation
│   ├── backfill.py           # Historical data backfill utility
│   └── pipeline.py           # Orchestrates the full run
└── data/
    ├── raw/                  # Timestamped raw pulls (not committed)
    ├── grid_stress.db        # SQLite database (not committed)
    ├── price_model.pkl       # Trained price forecast model
    └── stress_model.pkl      # Trained stress score model
```

---

## 🔑 Key Design Decisions

**Two independent data sources, not one.** EIA's API doesn't expose real-time locational price data — only demand, generation, and interchange. Rather than settle for one incomplete source, the pipeline combines EIA (a U.S. government dataset) with GridStatus.io (an ISO-market data specialist) — a more realistic reflection of how real analysts stitch together multiple imperfect sources.

**Raw and clean tables are kept separate.** `raw_eia` and `raw_gridstatus` preserve exactly what each API returned, for auditability. `fact_grid_hourly` is the transformed, analysis-ready table. This separation is standard data-engineering practice, not just extra structure.

**Validation is a first-class step, not an afterthought.** The pipeline checks for missing hours, out-of-range values, and — notably — caught a real, recurring pattern in the live data: EIA publishes Net Generation and Total Interchange with more delay than Demand and Day-Ahead Forecast, due to downstream settlement requirements. This asymmetry is logged, not hidden.

**Left joins over inner joins.** An early version used an inner join between demand and price data, which silently dropped valid rows whenever one source lagged behind the other. Switching to a left join anchored on demand data preserved every available hour, with honest `NULL`s where a source hadn't caught up yet — rather than fabricating or discarding data.

**No feature leakage.** All rolling statistics are computed using `.shift(1)` before the rolling window, ensuring no feature at hour *t* can see information from hour *t* itself — a common and easy-to-miss mistake in time-series feature engineering.

**Two forecasting targets, not one.** In addition to next-hour price, the project defines a custom composite **Grid Stress Score** (0–100) combining price deviation, demand-to-generation tightness, and congestion volatility — a more original signal than price alone, and one that required an explicit, defensible weighting decision.

**Historical backfill over waiting.** Rather than waiting days for the hourly scheduler to accumulate enough training data, the pipeline includes a backfill utility that pulls 30 days of history in minutes, using each API's own historical archive — turning a week-long wait into a same-day deliverable.

---

## 📊 Model Performance

Both models are `HistGradientBoostingRegressor`, chosen for their native handling of missing feature values — important given real-world API reporting gaps — evaluated against a naive persistence baseline (predict next hour = current hour) on a time-ordered, non-shuffled train/test split.

| Model | Training rows | Baseline MAE | Model MAE | Improvement |
|---|---|---|---|---|
| Next-hour price forecast | 651 | 12.21 | 7.99 | **34.6%** |
| Next-hour grid stress score | 613 | 20.13 | 6.91 | **65.7%** |

**Feature set (19 features):** lag values (1/3/6/24hr) for price and demand, rolling mean/std (3/24hr), hour-of-day, day-of-week, weekend flag, forecast error (actual vs. day-ahead demand forecast), and interchange ratio.

*Note: the price model's RMSE is notably higher than its MAE, indicating strong average performance with larger misses during rare price spikes — an expected limitation given how infrequent extreme spikes are in the training window, and a natural direction for future improvement (e.g., a separate spike-classification model).*

---

## 🖥️ Dashboard

The Streamlit dashboard (`app.py`) displays:
- Live demand, price, and next-hour forecasts as headline metrics
- A 7-day price & demand trend chart
- A grid stress score trend chart with a high-stress threshold marker
- Model performance summary and permutation-based feature importance

---

## ⚙️ Automation

The full pipeline (`ingest/pipeline.py`) runs **hourly and unattended** via Windows Task Scheduler:
1. Fetch latest data from both APIs (independent error handling per source)
2. Save timestamped raw CSVs
3. Load into SQLite with constraint-based deduplication
4. Run validation checks and log any issues
5. Transform and merge into `fact_grid_hourly`

All runs are logged to `pipeline.log`. The pipeline is **idempotent** — safe to re-run at any time without creating duplicate data — and **fault-tolerant**: a real EIA `504 Gateway Timeout` encountered during development did not crash the pipeline or block the GridStatus half of the run, proving the error-isolation design under an actual live failure.

---

## 🚧 Challenges & How They Were Solved

| Challenge | Resolution |
|---|---|
| ERCOT's public data portal blocked automated requests (Incapsula bot protection) | Pivoted to CAISO and GridStatus.io's hosted API, which avoids direct scraping |
| EIA API has no real-time price endpoint | Combined with a second, purpose-built ISO market data source instead |
| Inner joins silently dropped valid rows during source reporting lag | Switched to left joins anchored on the more reliable source |
| Rolling-window features caused data leakage | Added `.shift(1)` before all rolling calculations |
| Sparse early-stage data made 24hr rolling windows unusable | Built a historical backfill utility instead of waiting days for natural accumulation |
| `HistGradientBoostingRegressor` has no built-in feature importances | Used `sklearn.inspection.permutation_importance` instead |

---

## 🔮 Future Work

- Automated model retraining on a schedule as new data accumulates
- Migrate from SQLite to PostgreSQL for production-scale concurrent access
- Add a dedicated classification model for rare, high-impact price spikes
- Extend to additional CAISO hubs or a second ISO (e.g., PJM) for cross-region comparison
- Deploy the dashboard publicly (Streamlit Community Cloud) with the pipeline running on a cloud scheduler instead of a local machine

---

## 📎 Data Sources

- [U.S. Energy Information Administration (EIA) API](https://www.eia.gov/opendata/)
- [GridStatus.io](https://www.gridstatus.io/)

---

## 🧑‍💻 Author

Built as an end-to-end portfolio project demonstrating real-time API integration, database design, data validation, time-series feature engineering, forecasting, and dashboard deployment.
