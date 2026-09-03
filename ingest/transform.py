from datetime import datetime, timezone
import pandas as pd
from ingest.db import get_connection


def load_raw_from_db() -> tuple:
    conn = get_connection()
    df_eia = pd.read_sql("SELECT * FROM raw_eia", conn)
    df_gs = pd.read_sql("SELECT * FROM raw_gridstatus", conn)
    conn.close()
    return df_eia, df_gs


def build_fact_table(df_eia: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
    df_eia = df_eia.copy()
    df_eia["value"] = pd.to_numeric(df_eia["value"], errors="coerce")

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

    numeric_cols = ["demand_mwh", "day_ahead_forecast_mwh", "net_generation_mwh", "total_interchange_mwh"]
    for col in numeric_cols:
        if col in eia_wide.columns:
            eia_wide[col] = pd.to_numeric(eia_wide[col], errors="coerce")

    df_gs = df_gs.copy()
    df_gs["interval_start_utc"] = pd.to_datetime(df_gs["interval_start_utc"], utc=True)
    df_gs["hour_utc"] = df_gs["interval_start_utc"].dt.floor("h")
    for col in ["lmp", "congestion"]:
        df_gs[col] = pd.to_numeric(df_gs[col], errors="coerce")

    gs_hourly = df_gs.groupby("hour_utc").agg(
        avg_lmp=("lmp", "mean"),
        max_lmp=("lmp", "max"),
        avg_congestion=("congestion", "mean"),
    ).reset_index()

    fact = pd.merge(eia_wide, gs_hourly, on="hour_utc", how="left")

    fact["hour_utc"] = fact["hour_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    fact["created_at"] = datetime.now(timezone.utc).isoformat()

    return fact


def load_fact_table(fact: pd.DataFrame) -> int:
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
