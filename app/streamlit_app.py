"""Streamlit chat UI. OWNER: C.  Run: streamlit run app/streamlit_app.py"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for Streamlit Cloud

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
try:  # Streamlit Community Cloud secrets; locally there's usually no secrets.toml
    os.environ.setdefault("ANTHROPIC_API_KEY", st.secrets["ANTHROPIC_API_KEY"])
except Exception:
    pass

from agent.agent import respond  # noqa: E402

st.set_page_config(page_title="moomoo SG Margin Risk Assistant")
st.title("Margin Risk Assistant")
st.caption("Demo only. Margin ratios are documented assumptions, not live moomoo rates. Not investment advice.")

# Healthy, past the 48h clock, inside the 48h clock, below soft edge. See the README's demo table.
account_id = st.sidebar.selectbox("Demo account", ["M-001", "M-003", "M-006", "M-008"])

if st.session_state.get("account_id") != account_id:
    st.session_state.account_id = account_id
    st.session_state.api_messages = []
    st.session_state.display = []

for role, text in st.session_state.display:
    st.chat_message(role).markdown(text)

if prompt := st.chat_input("Ask about your margin, e.g. 'Am I going to get liquidated?'"):
    st.chat_message("user").markdown(prompt)
    st.session_state.display.append(("user", prompt))
    st.session_state.api_messages.append({"role": "user", "content": prompt})
    with st.spinner("Checking your account..."):
        response = respond(st.session_state.api_messages, account_id)
    with st.chat_message("assistant"):
        st.markdown(response.answer)
        # TODO(C): citations panel + margin gauge
        if response.tools_called:
            with st.expander("Tool calls"):
                st.json(response.tools_called)
        if response.case_summary:
            with st.expander("Risk desk case"):
                st.json(response.case_summary)
    st.session_state.display.append(("assistant", response.answer))
