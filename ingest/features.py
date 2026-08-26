import pandas as pd
import numpy as np


def load_fact_table():
    import sqlite3
    conn = sqlite3.connect("data/grid_stress.db")
    df = pd.read_sql("SELECT * FROM fact_grid_hourly ORDER BY hour_utc", conn)
    conn.close()
    df["hour_utc"] = pd.to_datetime(df["hour_utc"])
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("hour_utc").reset_index(drop=True)

    df["hour_of_day"] = df["hour_utc"].dt.hour
    df["day_of_week"] = df["hour_utc"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    df["forecast_error_mwh"] = df["demand_mwh"] - df["day_ahead_forecast_mwh"]
    df["interchange_ratio"] = df["total_interchange_mwh"] / df["demand_mwh"]

    for lag in [1, 3, 6, 24]:
        df[f"avg_lmp_lag{lag}"] = df["avg_lmp"].shift(lag)
        df[f"demand_mwh_lag{lag}"] = df["demand_mwh"].shift(lag)

    for window in [3, 24]:
        df[f"avg_lmp_roll_mean{window}"] = df["avg_lmp"].shift(1).rolling(window, min_periods=max(2, window//4)).mean()
        df[f"avg_lmp_roll_std{window}"] = df["avg_lmp"].shift(1).rolling(window, min_periods=max(2, window//4)).std()
        df[f"demand_mwh_roll_mean{window}"] = df["demand_mwh"].shift(1).rolling(window, min_periods=max(2, window//4)).mean()

    df["target_price_next_hour"] = df["avg_lmp"].shift(-1)

    # --- Stress score: back to full 24hr window now that we have real history ---
    roll_mean_24 = df["avg_lmp"].shift(1).rolling(24, min_periods=6).mean()
    price_stress = (df["avg_lmp"] - roll_mean_24) / roll_mean_24.abs().replace(0, np.nan)

    demand_stress = (df["demand_mwh"] - df["net_generation_mwh"]) / df["demand_mwh"]

    congestion_roll = df["avg_congestion"].abs().rolling(24, min_periods=6).mean()
    volatility_stress = df["avg_congestion"].abs() / congestion_roll.replace(0, np.nan)

    df["stress_score"] = (
        price_stress.rank(pct=True) * 100 * 0.4
        + demand_stress.rank(pct=True) * 100 * 0.35
        + volatility_stress.rank(pct=True) * 100 * 0.25
    )

    df["target_stress_next_hour"] = df["stress_score"].shift(-1)

    return df


if __name__ == "__main__":
    df = load_fact_table()
    print("Raw fact table shape:", df.shape)
    featured = engineer_features(df)
    print("Featured shape:", featured.shape)
    print(featured.tail(10))
