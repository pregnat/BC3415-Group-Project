"""The human risk desk's view of escalated cases. OWNER: C.

Streamlit shows this as a second page because it sits in app/pages/ next to the main file.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for Streamlit Cloud

import streamlit as st

from agent.escalation import list_cases  # noqa: E402

st.set_page_config(page_title="Risk desk · moomoo SG Margin Risk Assistant")
st.title("Risk desk")
st.caption("Cases the assistant escalated, newest first, with the margin snapshot taken when each was opened.")

cases = list_cases()
if not cases:
    st.info("No cases yet. They appear here when the assistant escalates or a customer presses 'Talk to a human'.")
    st.stop()

reasons = sorted({c["reason"] for c in cases})
chosen = st.multiselect("Reason", reasons, default=reasons)
shown = [c for c in cases if c["reason"] in chosen]

st.dataframe(
    [
        {
            "Case": c["case_id"],
            "Account": c["account_id"],
            "Reason": c["reason"],
            "Opened": c["created_at"][:16],
            "Status at opening": (c["margin_snapshot"] or {}).get("status"),
            "Equity": (c["margin_snapshot"] or {}).get("equity"),
            "Summary": c["summary"],
        }
        for c in shown
    ],
    hide_index=True,
    use_container_width=True,
)

for case in shown:
    with st.expander(f"{case['case_id']} · {case['account_id']} · {case['reason']}"):
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
            cols = st.columns(3)
            cols[0].metric("Equity", f"{snapshot['equity']:,.2f}")
            cols[1].metric("Maintenance", f"{snapshot['mm_req']:,.2f}")
            cols[2].metric("Soft edge", f"{snapshot['se_req']:,.2f}")
        st.json(case, expanded=False)
