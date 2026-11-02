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

from agent.agent import chat  # noqa: E402

st.set_page_config(page_title="moomoo SG Margin Risk Assistant")
st.title("Margin Risk Assistant")
st.caption("Demo only. Margin ratios are documented assumptions, not live moomoo rates. Not investment advice.")

# TODO(C): replace with the demo-scenario account list from data/accounts.db
account_id = st.sidebar.selectbox("Demo account", ["ACC-001", "ACC-002", "ACC-003"])

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
        reply, tool_calls = chat(st.session_state.api_messages, account_id)
    with st.chat_message("assistant"):
        st.markdown(reply)
        if tool_calls:
            with st.expander("Tool calls"):
                st.json(tool_calls)
    st.session_state.display.append(("assistant", reply))
