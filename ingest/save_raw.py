import os
from datetime import datetime, timezone
import pandas as pd

RAW_DIR = "data/raw"

def save_raw(df: pd.DataFrame, source: str) -> str:
    """
    Save a DataFrame to data/raw/ with a timestamped filename.
    source: short label like 'eia' or 'gridstatus', used in the filename.
    Returns the path the file was saved to.
    """
    os.makedirs(RAW_DIR, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{source}_{timestamp}.csv"
    filepath = os.path.join(RAW_DIR, filename)

    df.to_csv(filepath, index=False)
    print(f"Saved {len(df)} rows to {filepath}")

    return filepath
