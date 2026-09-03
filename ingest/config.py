import os
from dotenv import load_dotenv

def get_secret(key: str) -> str:
    """
    Reads a secret from .env locally (via python-dotenv), or from
    Streamlit's secrets manager when running on Streamlit Cloud.
    This lets the same fetch functions work in both the local
    scheduled pipeline and the deployed dashboard.
    """
    load_dotenv()
    value = os.getenv(key)
    if value:
        return value

    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return None
