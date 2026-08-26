import sqlite3
import os

DB_PATH = "data/grid_stress.db"


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def initialize_schema():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_eia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            respondent TEXT NOT NULL,
            respondent_name TEXT,
            type TEXT NOT NULL,
            type_name TEXT,
            value REAL,
            value_units TEXT,
            ingested_at TEXT NOT NULL,
            UNIQUE(period, respondent, type)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_gridstatus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interval_start_utc TEXT NOT NULL,
            interval_end_utc TEXT NOT NULL,
            market TEXT,
            location TEXT NOT NULL,
            location_type TEXT,
            lmp REAL,
            energy REAL,
            congestion REAL,
            loss REAL,
            ghg REAL,
            ingested_at TEXT NOT NULL,
            UNIQUE(interval_start_utc, location)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_grid_hourly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour_utc TEXT NOT NULL UNIQUE,
            demand_mwh REAL,
            day_ahead_forecast_mwh REAL,
            net_generation_mwh REAL,
            total_interchange_mwh REAL,
            avg_lmp REAL,
            max_lmp REAL,
            avg_congestion REAL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"Schema initialized at {DB_PATH}")


if __name__ == "__main__":
    initialize_schema()
