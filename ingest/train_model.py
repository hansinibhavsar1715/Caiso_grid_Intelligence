import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib

from ingest.features import load_fact_table, engineer_features

FEATURE_COLS = [
    "hour_of_day", "day_of_week", "is_weekend",
    "forecast_error_mwh", "interchange_ratio",
    "avg_lmp_lag1", "avg_lmp_lag3", "avg_lmp_lag6", "avg_lmp_lag24",
    "demand_mwh_lag1", "demand_mwh_lag3", "demand_mwh_lag6", "demand_mwh_lag24",
    "avg_lmp_roll_mean3", "avg_lmp_roll_std3",
    "avg_lmp_roll_mean24", "avg_lmp_roll_std24",
    "demand_mwh_roll_mean3", "demand_mwh_roll_mean24",
]


def prepare_training_data(target_col: str):
    df = load_fact_table()
    featured = engineer_features(df)
    clean = featured.dropna(subset=[target_col]).reset_index(drop=True)
    X = clean[FEATURE_COLS]
    y = clean[target_col]
    return X, y, clean


def train_and_evaluate(target_col: str, label: str):
    X, y, clean = prepare_training_data(target_col)

    print(f"\n=== {label} ===")
    print(f"Usable rows (target present): {len(X)}")
    print(f"Feature completeness:\n{X.notna().mean().round(2)}")

    if len(X) < 20:
        print("WARNING: very few usable rows - metrics will be unstable. "
              "Treat this as a v1 baseline, retrain once more data accumulates.")

    if len(X) < 5:
        print("Not enough data to train yet. Skipping.")
        return None, None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )

    baseline_series = X_test["avg_lmp_lag1"].ffill().bfill()
    baseline_mae = mean_absolute_error(y_test, baseline_series)

    model = HistGradientBoostingRegressor(
        max_iter=100, max_depth=3, learning_rate=0.1, random_state=42
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    model_mae = mean_absolute_error(y_test, preds)
    model_rmse = mean_squared_error(y_test, preds) ** 0.5

    print(f"Naive baseline MAE:  {baseline_mae:.2f}")
    print(f"Model MAE:           {model_mae:.2f}")
    print(f"Model RMSE:          {model_rmse:.2f}")
    print(f"Improvement over baseline: {(1 - model_mae/baseline_mae)*100:.1f}%")

    return model, {"baseline_mae": baseline_mae, "model_mae": model_mae, "model_rmse": model_rmse}


if __name__ == "__main__":
    price_model, price_metrics = train_and_evaluate("target_price_next_hour", "Price Forecast")
    if price_model:
        joblib.dump(price_model, "data/price_model.pkl")

    stress_model, stress_metrics = train_and_evaluate("target_stress_next_hour", "Stress Score Forecast")
    if stress_model:
        joblib.dump(stress_model, "data/stress_model.pkl")
