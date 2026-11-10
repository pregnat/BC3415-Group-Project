"""Streamlit entry point. OWNER: C.  Run: streamlit run app/streamlit_app.py

Sets up the environment, then routes to the two pages: the customer assistant (app/assistant.py)
and the human risk desk (app/risk_desk.py).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for Streamlit Cloud

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
try:  # Streamlit Community Cloud secrets; locally there's usually no secrets.toml
    os.environ.setdefault("ANTHROPIC_API_KEY", st.secrets["ANTHROPIC_API_KEY"])
    os.environ.setdefault("CLAUDE_MODEL", st.secrets.get("CLAUDE_MODEL", "claude-haiku-5-5"))
except Exception:
    pass

st.set_page_config(page_title="Margin Risk Assistant", page_icon=":material/shield:", layout="centered")
APP_DIR = Path(__file__).parent
st.navigation([
    st.Page(APP_DIR / "assistant.py", title="Assistant", icon=":material/forum:", default=True),
    st.Page(APP_DIR / "risk_desk.py", title="Risk desk", icon=":material/support_agent:"),
]).run()
