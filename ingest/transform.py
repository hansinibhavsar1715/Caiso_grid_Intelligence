from datetime import datetime, timezone
import pandas as pd
from ingest.db import get_connection


def load_raw_from_db() -> tuple:
    """Pulls all raw_eia and raw_gridstatus rows from SQLite as DataFrames."""
    conn = get_connection()
    df_eia = pd.read_sql("SELECT * FROM raw_eia", conn)
    df_gs = pd.read_sql("SELECT * FROM raw_gridstatus", conn)
    conn.close()
    return df_eia, df_gs


def build_fact_table(df_eia: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
    """
    Pivots EIA long format to wide (one row per hour), resamples
    GridStatus 5-min data to hourly, and joins them into one
    analysis-ready DataFrame. Uses a LEFT join anchored on EIA hours
    so demand rows aren't dropped just because NG/TI or price data
    hasn't fully caught up yet.
    """
    eia_wide = df_eia.pivot_table(
        index="period", columns="type", values="value", aggfunc="first"
    ).reset_index()

    eia_wide = eia_wide.rename(columns={
        "period": "hour_utc",
        "D": "demand_mwh",
        "DF": "day_ahead_forecast_mwh",
        "NG": "net_generation_mwh",
        "TI": "total_interchange_mwh",
    })

    eia_wide["hour_utc"] = pd.to_datetime(eia_wide["hour_utc"], format="%Y-%m-%dT%H", utc=True)

    df_gs = df_gs.copy()
    df_gs["interval_start_utc"] = pd.to_datetime(df_gs["interval_start_utc"], utc=True)
    df_gs["hour_utc"] = df_gs["interval_start_utc"].dt.floor("h")

    gs_hourly = df_gs.groupby("hour_utc").agg(
        avg_lmp=("lmp", "mean"),
        max_lmp=("lmp", "max"),
        avg_congestion=("congestion", "mean"),
    ).reset_index()

    # LEFT join: keep every EIA hour, even if price data isn't there yet
    fact = pd.merge(eia_wide, gs_hourly, on="hour_utc", how="left")

    fact["hour_utc"] = fact["hour_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    fact["created_at"] = datetime.now(timezone.utc).isoformat()

    return fact


def load_fact_table(fact: pd.DataFrame) -> int:
    """Inserts rows into fact_grid_hourly, skipping duplicates by hour_utc."""
    import sqlite3
    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    for _, row in fact.iterrows():
        try:
            cursor.execute("""
                INSERT INTO fact_grid_hourly
                    (hour_utc, demand_mwh, day_ahead_forecast_mwh,
                     net_generation_mwh, total_interchange_mwh,
                     avg_lmp, max_lmp, avg_congestion, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["hour_utc"], row.get("demand_mwh"), row.get("day_ahead_forecast_mwh"),
                row.get("net_generation_mwh"), row.get("total_interchange_mwh"),
                row.get("avg_lmp"), row.get("max_lmp"), row.get("avg_congestion"), row["created_at"]
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print(f"fact_grid_hourly: inserted {inserted} new rows ({len(fact) - inserted} duplicates skipped)")
    return inserted
