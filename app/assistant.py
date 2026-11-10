"""The customer-facing assistant page. OWNER: C.  Run the app with: streamlit run app/streamlit_app.py

The account card, the what-if sliders and the weekend alert come straight from the engine, so they
work without an API call. Only the chat calls Claude.
"""
import streamlit as st

from agent.agent import respond
from agent.escalation import create_case, list_cases
from agent.faithfulness import unfaithful_numbers
from contracts import AgentResponse, MarginStatus
from engine.calendar import next_market_open
from engine.margin import get_account, liquidation_distance, margin_status, weekend_risk_check
from engine.price_checks import sessions_between
from engine.prices import get_prices

# Healthy, past the 48h clock, inside the 48h clock, below soft edge. See the README's demo table.
ACCOUNTS = {
    "M-001": "Healthy",
    "M-003": "48h clock passed",
    "M-006": "48h clock running",
    "M-008": "Below soft edge",
}
STATUS_BADGES = {
    "healthy": ":green-badge[:material/check_circle: Healthy]",
    "below_mm": ":orange-badge[:material/warning: Below maintenance]",
    "below_se": ":red-badge[:material/error: Below soft edge]",
}
RISK_LABELS = {
    "none": "No liquidation risk",
    "after_48h": "Liquidation possible once 48 hours below maintenance",
    "anytime": "Liquidation possible at any time",
    "immediate": "Liquidation possible immediately",
}
AVATARS = {"user": ":material/person:", "assistant": ":material/support_agent:"}


def suggested_questions(account_id: str) -> list[str]:
    """The demo scenarios that fit this account's holdings."""
    tickers = {p.ticker for p in get_account(account_id).positions}
    ticker = "NVDA" if "NVDA" in tickers else sorted(tickers)[0]
    return [
        "Am I at risk of liquidation?",
        f"It's Friday. If {ticker} drops 8%, what happens?",
        "What's the difference between maintenance and soft-edge margin?",
        f"Should I sell {ticker} to fix this?",
        "You liquidated my shares without warning. I want compensation.",
    ]


def price_age_note(status: MarginStatus) -> str:
    """How old the snapshot prices are at the demo clock, from the price data-quality check."""
    quotes = get_prices([p.ticker for p in status.positions])
    oldest = min(q.timestamp.date() for q in quotes.values())
    sessions = sessions_between(oldest, status.as_of.date())
    age = f", {sessions} trading sessions old" if sessions else ""
    return f"Prices from the {oldest:%d %b} snapshot{age}."


def render_account_card(status: MarginStatus) -> None:
    """Equity against the requirements, straight from the engine (no API call)."""
    with st.container(border=True):
        left, right = st.columns([3, 2], vertical_alignment="center")
        left.markdown(f"#### Account {status.account_id}")
        right.markdown(STATUS_BADGES[status.status])
        cols = st.columns(4)
        cols[0].metric("Equity", f"{status.equity:,.2f}")
        cols[1].metric("Maintenance", f"{status.mm_req:,.2f}")
        cols[2].metric("Soft edge", f"{status.se_req:,.2f}")
        cols[3].metric("Hours below", f"{status.hours_below_mm:,.0f}" if status.hours_below_mm else "–")
        coverage = status.equity / status.mm_req if status.mm_req else 1.0
        coverage_text = f"Equity is {coverage:.0%} of maintenance" if status.equity >= 0 else "Equity is negative"
        st.progress(
            min(max(coverage, 0.0), 1.0),
            text=f"{coverage_text} · {RISK_LABELS[status.liquidation_risk]}",
        )
        positions = ", ".join(f"{p.quantity:g} {p.ticker} at {p.price:,.2f}" for p in status.positions)
        st.caption(
            f"{positions} · {status.currency} at {status.as_of:%a %d %b %H:%M} UTC · {price_age_note(status)}"
        )


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
        f"It is normally lowered again after the market reopens ({lowered:%a %d %b %H:%M} UTC).",
        icon=":material/event_busy:",
    )


def render_what_if(account_id: str) -> None:
    """Price shocks run through the engine directly, so customers can explore without the chatbot."""
    with st.sidebar.expander("What-if: move a price", icon=":material/tune:"):
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
    if st.sidebar.button("Talk to a human", icon=":material/headset_mic:", use_container_width=True):
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
    with st.sidebar.expander(f"Your risk desk cases ({len(cases)})", icon=":material/folder_open:"):
        if not cases:
            st.caption("No cases for this account.")
        for case in cases:
            st.markdown(f"**{case['case_id']}** · {case['reason']} · {case['created_at'][:16]}")
            st.caption(case["summary"])


def render_details(response: AgentResponse, question: str) -> None:
    """Number check, sources, risk-desk case and tool trace under an assistant message."""
    unsupported = unfaithful_numbers(response, question)
    if unsupported:
        st.warning(
            f"These figures don't match the margin engine: {', '.join(unsupported)}. "
            "Check them against your account above or ask again.",
            icon=":material/report:",
        )
    elif response.tools_called:
        st.caption(":material/verified: Every figure in this answer matches the margin engine or the help centre.")
    if response.citations:
        st.markdown("**Sources** · " + " · ".join(f"[{c['title']}]({c['url']})" for c in response.citations))
    if response.case_summary:
        case = response.case_summary
        st.info(
            f"Escalated to the risk desk · case **{case['case_id']}** · reason: {case['reason']}",
            icon=":material/support_agent:",
        )
        if show_trace:
            with st.expander("Case sent to the risk desk"):
                st.json(case)
    if show_trace and response.tools_called:
        with st.expander(f"How the agent answered · {len(response.tools_called)} tool calls", icon=":material/build:"):
            for call in response.tools_called:
                call_status = "error" if call["is_error"] else "ok"
                st.markdown(f"`{call['name']}` · {call_status}")
                st.json({"input": call["input"], "output": call["output"]}, expanded=False)


# --- Sidebar -----------------------------------------------------------------------------------

account_id = st.sidebar.selectbox(
    "Customer account", list(ACCOUNTS), format_func=lambda a: f"{a} · {ACCOUNTS[a]}"
)
if st.session_state.get("account_id") != account_id:
    st.session_state.account_id = account_id
    st.session_state.api_messages = []
    st.session_state.turns = []  # list of (role, text, AgentResponse | None)

render_what_if(account_id)
render_human_handoff(account_id)
render_cases(account_id)
st.sidebar.divider()
show_trace = st.sidebar.toggle("Show how the agent answered", value=True)
st.sidebar.caption("Demo accounts on a frozen price snapshot. Margin ratios are documented assumptions, not live moomoo rates.")

# --- Main page ---------------------------------------------------------------------------------

st.title("Margin Risk Assistant")
st.caption("Ask about your margin, liquidation risk or moomoo's rules. Not investment advice.")

status = margin_status(account_id)
render_account_card(status)
render_weekend_alert(account_id, status)

question = ""
for role, text, response in st.session_state.turns:
    with st.chat_message(role, avatar=AVATARS[role]):
        st.markdown(text)
        if response is not None:
            render_details(response, question)
    question = text if role == "user" else question

suggested = None
if not st.session_state.turns:
    suggested = st.pills(
        "Try asking", suggested_questions(account_id), key=f"suggest_{account_id}", label_visibility="visible"
    )

if prompt := st.chat_input("Ask about your margin, e.g. 'Am I going to get liquidated?'") or suggested:
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.markdown(prompt)
    st.session_state.turns.append(("user", prompt, None))
    st.session_state.api_messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner("Checking your account..."):
            try:
                response = respond(st.session_state.api_messages, account_id)
            except Exception as e:  # show API/config errors instead of a blank page
                st.error(
                    f"The assistant hit an error: {e}. Use **Talk to a human** in the sidebar to reach the risk desk.",
                    icon=":material/cloud_off:",
                )
                st.session_state.api_messages.pop()  # drop the unanswered turn so history stays valid
                st.session_state.turns.pop()
                st.stop()
        st.markdown(response.answer)
        render_details(response, prompt)
    st.session_state.turns.append(("assistant", response.answer, response))
    if suggested:
        st.session_state.pop(f"suggest_{account_id}", None)
        st.rerun()  # hide the suggestions now that the chat has started
