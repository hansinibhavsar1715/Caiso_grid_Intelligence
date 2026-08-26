import logging
from datetime import datetime, timedelta, timezone

from ingest.eia_fetch import fetch_eia_caiso
from ingest.gridstatus_fetch import fetch_caiso_lmp
from ingest.save_raw import save_raw
from ingest.load_to_db import load_eia_csv, load_gridstatus_csv
from ingest.validate import run_validation
from ingest.transform import load_raw_from_db, build_fact_table, load_fact_table

logging.basicConfig(
    filename="pipeline.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def run_ingestion():
    """Fetches latest EIA + GridStatus data and saves to raw CSVs."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    eia_start = yesterday.strftime("%Y-%m-%dT%H")
    eia_end = now.strftime("%Y-%m-%dT%H")
    gs_start = yesterday.strftime("%Y-%m-%d")
    gs_end = now.strftime("%Y-%m-%d")

    results = {"eia": None, "gridstatus": None}

    try:
        df_eia = fetch_eia_caiso(start=eia_start, end=eia_end)
        path = save_raw(df_eia, source="eia")
        results["eia"] = {"status": "success", "rows": len(df_eia), "path": path}
        logger.info(f"EIA fetch succeeded: {len(df_eia)} rows -> {path}")
    except Exception as e:
        results["eia"] = {"status": "failed", "error": str(e)}
        logger.error(f"EIA fetch failed: {e}")

    try:
        df_gs = fetch_caiso_lmp(start=gs_start, end=gs_end)
        path = save_raw(df_gs, source="gridstatus")
        results["gridstatus"] = {"status": "success", "rows": len(df_gs), "path": path}
        logger.info(f"GridStatus fetch succeeded: {len(df_gs)} rows -> {path}")
    except Exception as e:
        results["gridstatus"] = {"status": "failed", "error": str(e)}
        logger.error(f"GridStatus fetch failed: {e}")

    return results


def run_full_pipeline():
    """
    Full end-to-end run: fetch -> save raw -> load to SQL ->
    validate -> transform -> load fact table.
    This is the single function Task Scheduler will call.
    """
    logger.info("=== Pipeline run started ===")

    ingestion_results = run_ingestion()

    if ingestion_results["eia"]["status"] == "success":
        load_eia_csv(ingestion_results["eia"]["path"])
    if ingestion_results["gridstatus"]["status"] == "success":
        load_gridstatus_csv(ingestion_results["gridstatus"]["path"])

    df_eia, df_gs = load_raw_from_db()
    validation_summary = run_validation(df_eia, df_gs)

    if validation_summary["eia_issues"]:
        for issue in validation_summary["eia_issues"]:
            logger.warning(f"Validation: {issue}")
    if validation_summary["gridstatus_issues"]:
        for issue in validation_summary["gridstatus_issues"]:
            logger.warning(f"Validation: {issue}")

    fact = build_fact_table(df_eia, df_gs)
    inserted = load_fact_table(fact)

    logger.info(f"=== Pipeline run complete: {inserted} new fact rows ===")
    print(f"Pipeline run complete: {inserted} new fact rows added to fact_grid_hourly")

    return {
        "ingestion": ingestion_results,
        "validation": validation_summary,
        "fact_rows_inserted": inserted,
    }


if __name__ == "__main__":
    run_full_pipeline()
