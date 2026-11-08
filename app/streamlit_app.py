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
    os.environ.setdefault("CLAUDE_MODEL", st.secrets.get("CLAUDE_MODEL", "claude-haiku-5-5"))
except Exception:
    pass

from agent.agent import respond  # noqa: E402
from contracts import AgentResponse  # noqa: E402

st.set_page_config(page_title="moomoo SG Margin Risk Assistant")
st.title("Margin Risk Assistant")
st.caption("Demo only. Margin ratios are documented assumptions, not live moomoo rates. Not investment advice.")

# Healthy, past the 48h clock, inside the 48h clock, below soft edge. See the README's demo table.
ACCOUNTS = {
    "M-001": "Healthy",
    "M-003": "Below maintenance, past 48h",
    "M-006": "Below maintenance, 48h clock running",
    "M-008": "Below soft edge",
}
account_id = st.sidebar.selectbox("Demo account", list(ACCOUNTS), format_func=lambda a: f"{a} · {ACCOUNTS[a]}")
show_trace = st.sidebar.toggle("Show how the agent answered", value=True)

if st.session_state.get("account_id") != account_id:
    st.session_state.account_id = account_id
    st.session_state.api_messages = []
    st.session_state.turns = []  # list of (role, text, AgentResponse | None)


def render_details(response: AgentResponse) -> None:
    """Sources, risk-desk case and tool trace under an assistant message."""
    if response.citations:
        st.markdown("**Sources**")
        for c in response.citations:
            st.markdown(f"- [{c['title']}]({c['url']})")
    if response.case_summary:
        case = response.case_summary
        st.info(f"Escalated to the risk desk · case **{case['case_id']}** · reason: {case['reason']}")
        if show_trace:
            with st.expander("Case sent to the risk desk"):
                st.json(case)
    if show_trace and response.tools_called:
        with st.expander(f"Tools called ({len(response.tools_called)})"):
            for call in response.tools_called:
                status = "error" if call["is_error"] else "ok"
                st.markdown(f"`{call['name']}` · {status}")
                st.json({"input": call["input"], "output": call["output"]}, expanded=False)


for role, text, response in st.session_state.turns:
    with st.chat_message(role):
        st.markdown(text)
        if response is not None:
            render_details(response)

if prompt := st.chat_input("Ask about your margin, e.g. 'Am I going to get liquidated?'"):
    st.chat_message("user").markdown(prompt)
    st.session_state.turns.append(("user", prompt, None))
    st.session_state.api_messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        with st.spinner("Checking your account..."):
            try:
                response = respond(st.session_state.api_messages, account_id)
            except Exception as e:  # show API/config errors instead of a blank page
                st.error(f"The assistant hit an error: {e}")
                st.session_state.api_messages.pop()  # drop the unanswered turn so history stays valid
                st.stop()
        st.markdown(response.answer)
        render_details(response)
    st.session_state.turns.append(("assistant", response.answer, response))
