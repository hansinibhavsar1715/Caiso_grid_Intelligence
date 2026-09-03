
import requests
import pandas as pd
from ingest.config import get_secret


def fetch_eia_caiso(start: str, end: str) -> pd.DataFrame:
    api_key = get_secret("EIA_API_KEY")

    if not api_key:
        raise ValueError("EIA_API_KEY not found - check your .env file or Streamlit secrets")

    url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    params = {
        "api_key": api_key,
        "frequency": "hourly",
        "data[]": "value",
        "facets[respondent][]": "CISO",
        "start": start,
        "end": end,
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    records = response.json()["response"]["data"]
    df = pd.DataFrame(records)

    if df.empty:
        raise ValueError(f"EIA returned no data for {start} to {end}")

    return df