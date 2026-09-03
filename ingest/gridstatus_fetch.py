
import gridstatusio as gs
from ingest.config import get_secret

HUBS = ["TH_NP15_GEN-APND", "TH_SP15_GEN-APND", "TH_ZP26_GEN-APND"]


def fetch_caiso_lmp(start: str, end: str):
    api_key = get_secret("GRIDSTATUS_API_KEY")

    if not api_key:
        raise ValueError("GRIDSTATUS_API_KEY not found - check your .env file or Streamlit secrets")

    client = gs.GridStatusClient(api_key=api_key)

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