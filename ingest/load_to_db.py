import sqlite3
from datetime import datetime, timezone
import pandas as pd

from ingest.db import get_connection


def load_eia_csv(filepath: str) -> int:
    """
    Loads an EIA raw CSV into raw_eia, skipping duplicates.
    Returns number of rows actually inserted.
    """
    df = pd.read_csv(filepath)
    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    now = datetime.now(timezone.utc).isoformat()

    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO raw_eia
                    (period, respondent, respondent_name, type, type_name,
                     value, value_units, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["period"], row["respondent"], row.get("respondent-name"),
                row["type"], row.get("type-name"),
                row["value"], row.get("value-units"), now
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # duplicate row (already loaded) - skip silently
            pass

    conn.commit()
    conn.close()
    print(f"raw_eia: inserted {inserted} new rows ({len(df) - inserted} duplicates skipped)")
    return inserted


def load_gridstatus_csv(filepath: str) -> int:
    """
    Loads a GridStatus raw CSV into raw_gridstatus, skipping duplicates.
    Returns number of rows actually inserted.
    """
    df = pd.read_csv(filepath)
    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    now = datetime.now(timezone.utc).isoformat()

    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO raw_gridstatus
                    (interval_start_utc, interval_end_utc, market, location,
                     location_type, lmp, energy, congestion, loss, ghg, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["interval_start_utc"], row["interval_end_utc"], row.get("market"),
                row["location"], row.get("location_type"),
                row["lmp"], row["energy"], row["congestion"], row["loss"], row.get("ghg"),
                now
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print(f"raw_gridstatus: inserted {inserted} new rows ({len(df) - inserted} duplicates skipped)")
    return inserted
