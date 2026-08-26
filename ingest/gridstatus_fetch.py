import os
import gridstatusio as gs
from dotenv import load_dotenv

load_dotenv()
GRIDSTATUS_API_KEY = os.getenv("GRIDSTATUS_API_KEY")

HUBS = ["TH_NP15_GEN-APND", "TH_SP15_GEN-APND", "TH_ZP26_GEN-APND"]


def fetch_caiso_lmp(start: str, end: str):
    """
    Pull real-time 5-minute LMP price data for the 3 major
    CAISO trading hubs.
    start/end format: 'YYYY-MM-DD'
    """
    client = gs.GridStatusClient(api_key=GRIDSTATUS_API_KEY)

    df = client.get_dataset(
        dataset="caiso_lmp_real_time_5_min",
        start=start,
        end=end,
        filter_column="location",
        filter_value=HUBS,
        filter_operator="in",
    )

    if df.empty:
        raise ValueError(f"GridStatus returned no data for {start} to {end}")

    return df
