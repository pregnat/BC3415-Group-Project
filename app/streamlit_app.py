"""Streamlit chat UI. OWNER: C.  Run: streamlit run app/streamlit_app.py

The sidebar and the weekend alert come straight from the engine, so they work without an API call.
The risk desk's view of escalated cases is the second page, app/pages/risk_desk.py.
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

from agent.agent import respond  # noqa: E402
from agent.escalation import create_case, list_cases  # noqa: E402
from agent.faithfulness import unfaithful_numbers  # noqa: E402
from contracts import AgentResponse, MarginStatus  # noqa: E402
from engine.calendar import next_market_open  # noqa: E402
from engine.margin import get_account, liquidation_distance, margin_status, weekend_risk_check  # noqa: E402
from engine.price_checks import sessions_between  # noqa: E402
from engine.prices import get_prices  # noqa: E402

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

STATUS_LABELS = {"healthy": "Healthy", "below_mm": "Below maintenance", "below_se": "Below soft edge"}


def price_age_note(status: MarginStatus) -> str:
    """How old the snapshot prices are at the demo clock, from the price data-quality check."""
    quotes = get_prices([p.ticker for p in status.positions])
    oldest = min(q.timestamp.date() for q in quotes.values())
    sessions = sessions_between(oldest, status.as_of.date())
    age = f", {sessions} trading sessions old" if sessions else ""
    return f"Prices from the {oldest:%d %b} snapshot{age}."


def render_gauge(status: MarginStatus) -> None:
    """Equity against the maintenance requirement, straight from the engine (no API call)."""
    st.sidebar.subheader("Margin gauge")
    coverage = status.equity / status.mm_req if status.mm_req else 1.0
    st.sidebar.progress(
        min(max(coverage, 0.0), 1.0),
        text=f"{STATUS_LABELS[status.status]} · equity is {coverage:.0%} of maintenance",
    )
    left, right = st.sidebar.columns(2)
    left.metric("Equity", f"{status.equity:,.2f}")
    right.metric("Maintenance", f"{status.mm_req:,.2f}")
    left.metric("Soft edge", f"{status.se_req:,.2f}")
    if status.hours_below_mm:
        right.metric("Hours below", f"{status.hours_below_mm:,.0f}")
    st.sidebar.caption(
        f"{status.currency} at {status.as_of:%a %d %b %H:%M} UTC. {price_age_note(status)}"
    )


def render_what_if(account_id: str) -> None:
    """Price shocks run through the engine directly, so customers can explore without the chatbot."""
    with st.sidebar.expander("What-if: move a price"):
        shocks = {
            p.ticker: st.slider(f"{p.ticker} price change (%)", -50, 20, 0, key=f"shock_{account_id}_{p.ticker}") / 100
            for p in get_account(account_id).positions
        }
        distance = liquidation_distance(account_id, shocks)
        weekend = weekend_risk_check(account_id, shocks=shocks)
        st.metric("Equity after the move", f"{distance.stressed_equity:,.2f}")
        st.caption(
            f"With no move, a {distance.pct_drop_to_mm:.1%} fall in every holding reaches maintenance "
            f"and {distance.pct_drop_to_se:.1%} reaches the soft edge."
        )
        if weekend.is_pre_weekend:
            if weekend.would_breach:
                st.error(
                    f"Below the raised pre-weekend soft edge ({weekend.se_req_raised:,.2f}) "
                    f"by {weekend.shortfall_to_se_raised:,.2f}."
                )
            else:
                st.success(
                    f"Above the raised pre-weekend soft edge ({weekend.se_req_raised:,.2f}) "
                    f"by {weekend.excess_over_se_raised:,.2f}."
                )


def last_question() -> str:
    return next((text for role, text, _ in reversed(st.session_state.turns) if role == "user"), "")


def render_human_handoff(account_id: str) -> None:
    """A fallback that doesn't depend on the model deciding to escalate."""
    if st.sidebar.button("Talk to a human", use_container_width=True):
        question = last_question()
        case = create_case(
            account_id,
            "other",
            question or "(asked for a human from the app)",
            "Customer pressed 'Talk to a human' in the app."
            + (f" Their last question was: {question}" if question else " They hadn't asked a question yet."),
            timeline=[f"{len(st.session_state.turns)} chat messages before the handoff."],
        )
        st.sidebar.success(f"Case **{case.case_id}** opened. The risk desk will contact you.")


def render_cases(account_id: str) -> None:
    cases = list_cases(account_id)
    with st.sidebar.expander(f"Risk desk cases ({len(cases)})"):
        if not cases:
            st.caption("No cases for this account.")
        for case in cases:
            st.markdown(f"**{case['case_id']}** · {case['reason']} · {case['created_at'][:16]}")
            st.caption(case["summary"])


def render_weekend_alert(account_id: str, status: MarginStatus) -> None:
    """Proactive warning before the soft edge is raised for the weekend (a plan stretch goal)."""
    weekend = weekend_risk_check(account_id, status.as_of)
    if not weekend.would_breach:
        return
    lowered = next_market_open(status.as_of)
    st.warning(
        f"**Weekend alert:** moomoo may raise the soft edge before the close. At current prices your "
        f"equity ({weekend.equity:,.2f}) would be {weekend.shortfall_to_se_raised:,.2f} below the raised "
        f"requirement ({weekend.se_req_raised:,.2f}), so forced liquidation could happen immediately. "
        f"It is normally lowered again after the market reopens ({lowered:%a %d %b %H:%M} UTC)."
    )


if st.session_state.get("account_id") != account_id:
    st.session_state.account_id = account_id
    st.session_state.api_messages = []
    st.session_state.turns = []  # list of (role, text, AgentResponse | None)

status = margin_status(account_id)
render_gauge(status)
render_what_if(account_id)
render_human_handoff(account_id)
render_cases(account_id)
render_weekend_alert(account_id, status)


def render_details(response: AgentResponse, question: str) -> None:
    """Number check, sources, risk-desk case and tool trace under an assistant message."""
    unsupported = unfaithful_numbers(response, question)
    if unsupported:
        st.warning(
            f"These figures don't match the margin engine: {', '.join(unsupported)}. "
            "Check them in the sidebar or ask again."
        )
    elif response.tools_called:
        st.caption("✓ Every figure in this answer matches the margin engine or the help centre.")
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
                call_status = "error" if call["is_error"] else "ok"
                st.markdown(f"`{call['name']}` · {call_status}")
                st.json({"input": call["input"], "output": call["output"]}, expanded=False)


question = ""
for role, text, response in st.session_state.turns:
    with st.chat_message(role):
        st.markdown(text)
        if response is not None:
            render_details(response, question)
    question = text if role == "user" else question

if prompt := st.chat_input("Ask about your margin, e.g. 'Am I going to get liquidated?'"):
    st.chat_message("user").markdown(prompt)
    st.session_state.turns.append(("user", prompt, None))
    st.session_state.api_messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        with st.spinner("Checking your account..."):
            try:
                response = respond(st.session_state.api_messages, account_id)
            except Exception as e:  # show API/config errors instead of a blank page
                st.error(f"The assistant hit an error: {e}. Use **Talk to a human** in the sidebar to reach the risk desk.")
                st.session_state.api_messages.pop()  # drop the unanswered turn so history stays valid
                st.stop()
        st.markdown(response.answer)
        render_details(response, prompt)
    st.session_state.turns.append(("assistant", response.answer, response))
