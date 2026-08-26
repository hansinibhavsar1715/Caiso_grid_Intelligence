import streamlit as st
import pandas as pd
import sqlite3
import joblib
import plotly.graph_objects as go
from sklearn.inspection import permutation_importance

from ingest.features import engineer_features

st.set_page_config(page_title="Grid Stress Monitor", layout="wide")

@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect("data/grid_stress.db")
    df = pd.read_sql("SELECT * FROM fact_grid_hourly ORDER BY hour_utc", conn)
    conn.close()
    df["hour_utc"] = pd.to_datetime(df["hour_utc"])
    return df

@st.cache_resource
def load_models():
    price_model = joblib.load("data/price_model.pkl")
    stress_model = joblib.load("data/stress_model.pkl")
    return price_model, stress_model

FEATURE_COLS = [
    "hour_of_day", "day_of_week", "is_weekend",
    "forecast_error_mwh", "interchange_ratio",
    "avg_lmp_lag1", "avg_lmp_lag3", "avg_lmp_lag6", "avg_lmp_lag24",
    "demand_mwh_lag1", "demand_mwh_lag3", "demand_mwh_lag6", "demand_mwh_lag24",
    "avg_lmp_roll_mean3", "avg_lmp_roll_std3",
    "avg_lmp_roll_mean24", "avg_lmp_roll_std24",
    "demand_mwh_roll_mean3", "demand_mwh_roll_mean24",
]

df = load_data()
featured = engineer_features(df)
price_model, stress_model = load_models()

st.title("⚡ CAISO Grid Stress & Price Intelligence")
st.caption(f"Live pipeline: EIA demand data + GridStatus.io real-time pricing | Last data point: {df['hour_utc'].max()}")

# Most recent row WITH complete demand/price data (for display)
complete_rows = featured.dropna(subset=["demand_mwh", "avg_lmp"])
latest_complete = complete_rows.iloc[[-1]] if len(complete_rows) > 0 else featured.iloc[[-1]]

# True latest row (for prediction - features can handle some NaN)
latest_for_prediction = featured.iloc[[-1]]
latest_features = latest_for_prediction[FEATURE_COLS]

st.caption(f"Showing latest complete hour: {latest_complete['hour_utc'].values[0]} "
           f"(most recent pipeline data point: {latest_for_prediction['hour_utc'].values[0]}, may still be settling)")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Latest Demand (MWh)", f"{latest_complete['demand_mwh'].values[0]:,.0f}")

with col2:
    st.metric("Latest Avg Price ($/MWh)", f"${latest_complete['avg_lmp'].values[0]:,.2f}")

try:
    predicted_price = price_model.predict(latest_features)[0]
    with col3:
        st.metric("Predicted Next-Hour Price", f"${predicted_price:,.2f}")
except Exception:
    with col3:
        st.metric("Predicted Next-Hour Price", "N/A")

try:
    predicted_stress = stress_model.predict(latest_features)[0]
    with col4:
        risk_label = "🔴 High" if predicted_stress > 70 else "🟡 Moderate" if predicted_stress > 40 else "🟢 Low"
        st.metric("Predicted Stress Risk", risk_label, f"{predicted_stress:.0f}/100")
except Exception:
    with col4:
        st.metric("Predicted Stress Risk", "N/A")

st.divider()

recent = featured.tail(168)

tab1, tab2, tab3 = st.tabs(["Price & Demand", "Grid Stress Score", "Model Info"])

with tab1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=recent["hour_utc"], y=recent["demand_mwh"], name="Demand (MWh)", yaxis="y1"))
    fig.add_trace(go.Scatter(x=recent["hour_utc"], y=recent["avg_lmp"], name="Avg Price ($/MWh)", yaxis="y2"))
    fig.update_layout(
        yaxis=dict(title="Demand (MWh)"),
        yaxis2=dict(title="Price ($/MWh)", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1),
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=recent["hour_utc"], y=recent["stress_score"], name="Stress Score", fill="tozeroy"))
    fig2.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="High stress threshold")
    fig2.update_layout(yaxis=dict(title="Stress Score (0-100)"), height=450)
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("Model Performance (held-out test set)")
    st.write("**Price Forecast Model**: 34.6% MAE improvement over naive baseline (651 training hours)")
    st.write("**Stress Score Model**: 65.7% MAE improvement over naive baseline (613 training hours)")
    st.caption("Both models are HistGradientBoostingRegressor, trained on lag/rolling/calendar features from EIA + GridStatus.io data.")

    st.subheader("Top Price Model Features")
    with st.spinner("Computing feature importance..."):
        clean = featured.dropna(subset=FEATURE_COLS + ["target_price_next_hour"])
        X_sample = clean[FEATURE_COLS].tail(200)
        y_sample = clean["target_price_next_hour"].tail(200)

        result = permutation_importance(
            price_model, X_sample, y_sample, n_repeats=5, random_state=42
        )
        importances = pd.Series(result.importances_mean, index=FEATURE_COLS).sort_values(ascending=False)

    st.bar_chart(importances.head(8))
