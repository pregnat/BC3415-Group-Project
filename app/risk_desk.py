"""The human risk desk's view of escalated cases. OWNER: C.  Routed from app/streamlit_app.py."""
from collections import Counter

import streamlit as st

from agent.escalation import list_cases

REASON_LABELS = {
    "liquidation_dispute": "Liquidation dispute",
    "extension_request": "Extension request",
    "other": "Other",
}

st.title("Risk desk")
st.caption("Cases escalated by the assistant or by customers, newest first, with the margin snapshot taken at the time.")

cases = list_cases()
if not cases:
    st.info(
        "No cases yet. They appear here when the assistant escalates or a customer presses 'Talk to a human'.",
        icon=":material/inbox:",
    )
    st.stop()

counts = Counter(c["reason"] for c in cases)
cols = st.columns(1 + len(REASON_LABELS))
cols[0].metric("Open cases", len(cases), border=True)
for col, (reason, label) in zip(cols[1:], REASON_LABELS.items()):
    col.metric(label, counts.get(reason, 0), border=True)

chosen = st.pills(
    "Reason", list(REASON_LABELS), default=list(REASON_LABELS), selection_mode="multi",
    format_func=REASON_LABELS.get,
)
shown = [c for c in cases if c["reason"] in (chosen or [])]

st.dataframe(
    [
        {
            "Case": c["case_id"],
            "Account": c["account_id"],
            "Reason": REASON_LABELS.get(c["reason"], c["reason"]),
            "Opened": c["created_at"][:16].replace("T", " "),
            "Status at opening": (c["margin_snapshot"] or {}).get("status"),
            "Equity": (c["margin_snapshot"] or {}).get("equity"),
            "Summary": c["summary"],
        }
        for c in shown
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "Equity": st.column_config.NumberColumn(format="%,.2f"),
        "Summary": st.column_config.TextColumn(width="large"),
    },
)

for case in shown:
    title = f"{case['case_id']} · {case['account_id']} · {REASON_LABELS.get(case['reason'], case['reason'])}"
    with st.expander(title, icon=":material/description:"):
        st.markdown(f"**Customer said:** {case['customer_message']}")
        st.markdown(f"**Summary:** {case['summary']}")
        if case["rule_cited"]:
            st.markdown(f"**Rule cited:** {case['rule_cited']}")
        if case["timeline"]:
            st.markdown("**Timeline**")
            for event in case["timeline"]:
                st.markdown(f"- {event}")
        snapshot = case["margin_snapshot"] or {}
        if snapshot:
            metric_cols = st.columns(3)
            metric_cols[0].metric("Equity", f"{snapshot['equity']:,.2f}")
            metric_cols[1].metric("Maintenance", f"{snapshot['mm_req']:,.2f}")
            metric_cols[2].metric("Soft edge", f"{snapshot['se_req']:,.2f}")
        st.json(case, expanded=False)
