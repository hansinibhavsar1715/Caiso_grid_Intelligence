from datetime import datetime, timedelta, timezone

from ingest.eia_fetch import fetch_eia_caiso
from ingest.gridstatus_fetch import fetch_caiso_lmp
from ingest.save_raw import save_raw
from ingest.load_to_db import load_eia_csv, load_gridstatus_csv
from ingest.transform import load_raw_from_db, build_fact_table, load_fact_table


def backfill(days: int = 30):
    end = datetime.now(timezone.utc)

    for i in range(days):
        day_end = end - timedelta(days=i)
        day_start = day_end - timedelta(days=1)

        eia_start = day_start.strftime("%Y-%m-%dT%H")
        eia_end = day_end.strftime("%Y-%m-%dT%H")
        gs_start = day_start.strftime("%Y-%m-%d")
        gs_end = day_end.strftime("%Y-%m-%d")

        print(f"\n--- Backfilling day {i+1}/{days}: {gs_start} to {gs_end} ---")

        try:
            df_eia = fetch_eia_caiso(start=eia_start, end=eia_end)
            path = save_raw(df_eia, source="eia")
            load_eia_csv(path)
        except Exception as e:
            print(f"EIA backfill failed for this day: {e}")

        try:
            df_gs = fetch_caiso_lmp(start=gs_start, end=gs_end)
            path = save_raw(df_gs, source="gridstatus")
            load_gridstatus_csv(path)
        except Exception as e:
            print(f"GridStatus backfill failed for this day: {e}")

    # NEW: rebuild the fact table from ALL raw data now sitting in the DB
    print("\n--- Rebuilding fact_grid_hourly from all raw data ---")
    df_eia_all, df_gs_all = load_raw_from_db()
    fact = build_fact_table(df_eia_all, df_gs_all)
    inserted = load_fact_table(fact)
    print(f"Backfill complete. {inserted} new fact rows inserted.")


if __name__ == "__main__":
    backfill(days=30)
