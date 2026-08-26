import os
import requests
import pandas as pd
from dotenv import load_dotenv

def fetch_eia_caiso(start: str, end: str) -> pd.DataFrame:
    """
    Pull hourly demand, day-ahead forecast, net generation,
    and interchange for CAISO from the EIA API.
    start/end format: 'YYYY-MM-DDTHH'
    """
    load_dotenv()
    api_key = os.getenv("EIA_API_KEY")

    if not api_key:
        raise ValueError("EIA_API_KEY not found - check your .env file")

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
