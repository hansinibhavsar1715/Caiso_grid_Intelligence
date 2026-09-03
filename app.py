import streamlit as st
import pandas as pd
import joblib
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

from ingest.eia_fetch import fetch_eia_caiso
from ingest.gridstatus_fetch import fetch_caiso_lmp
from ingest.transform import build_fact_table
from ingest.features import engineer_features

st.set_page_config(page_title="Grid Stress Monitor", layout="wide")

FEATURE_COLS = [
    "hour_of_day", "day_of_week", "is_weekend",
    "forecast_error_mwh", "interchange_ratio",
    "avg_lmp_lag1", "avg_lmp_lag3", "avg_lmp_lag6", "avg_lmp_lag24",
    "demand_mwh_lag1", "demand_mwh_lag3", "demand_mwh_lag6", "demand_mwh_lag24",
    "avg_lmp_roll_mean3", "avg_lmp_roll_std3",
    "avg_lmp_roll_mean24", "avg_lmp_roll_std24",
    "demand_mwh_roll_mean3", "demand_mwh_roll_mean24",
]


@st.cache_data(ttl=900)  # refresh every 15 minutes - avoids hammering the APIs
def load_live_data():
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(days=3)  # need enough history for lag24/rolling24

    df_eia = fetch_eia_caiso(
        start=lookback.strftime("%Y-%m-%dT%H"),
        end=now.strftime("%Y-%m-%dT%H"),
    )
    df_gs = fetch_caiso_lmp(
        start=lookback.strftime("%Y-%m-%d"),
        end=now.strftime("%Y-%m-%d"),
    )

    fact = build_fact_table(df_eia, df_gs)
    fact["hour_utc"] = pd.to_datetime(fact["hour_utc"])
    return fact


@st.cache_resource
def load_models():
    price_model = joblib.load("data/price_model.pkl")
    stress_model = joblib.load("data/stress_model.pkl")
    return price_model, stress_model


st.title("⚡ CAISO Grid Stress & Price Intelligence")

with st.spinner("Fetching live grid data..."):
    df = load_live_data()
    featured = engineer_features(df)
    price_model, stress_model = load_models()

st.caption(f"Live pipeline: EIA demand data + GridStatus.io real-time pricing | "
           f"Data refreshes every 15 min | Last data point: {df['hour_utc'].max()}")

complete_rows = featured.dropna(subset=["demand_mwh", "avg_lmp"])
latest_complete = complete_rows.iloc[[-1]] if len(complete_rows) > 0 else featured.iloc[[-1]]
latest_for_prediction = featured.iloc[[-1]]
latest_features = latest_for_prediction[FEATURE_COLS]

st.caption(f"Showing latest complete hour: {latest_complete['hour_utc'].values[0]}")

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

recent = featured.tail(72)

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
    st.caption("Models trained offline on historical data; this dashboard fetches live data for inference only.")
