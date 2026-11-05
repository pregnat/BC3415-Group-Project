"""OWNER: C."""
from dataclasses import asdict
import json

from agent.escalation import CASES, create_case, list_cases
from engine.margin import margin_status


def test_case_created_with_snapshot():
    case = create_case("M-003", "liquidation_dispute", "You sold my shares!", "Dispute re: liquidation.")
    assert case.case_id.startswith("RISK-")
    assert case.margin_snapshot is not None
    assert CASES[case.case_id] is case


def test_case_summary_has_s4_fields():
    case = create_case(
        "M-003",
        "liquidation_dispute",
        "You liquidated my shares without warning. I want compensation.",
        "Customer disputes liquidation and asks for compensation.",
        timeline=["Customer reports shares sold on 6 Nov."],
        rule_cited="Below soft edge, forced liquidation may occur immediately.",
        cited_chunk_ids=["topic5_493#0"],
    )
    summary = json.loads(json.dumps(asdict(case), default=str))
    assert summary["margin_snapshot"]["equity"] == margin_status("M-003").equity
    assert summary["timeline"] and summary["rule_cited"] and summary["cited_chunk_ids"]


def test_cases_are_saved_and_listed_per_account():
    first = create_case("M-003", "extension_request", "Two more days?", "Extension request.")
    second = create_case("M-003", "liquidation_dispute", "You sold my shares!", "Dispute.")
    create_case("M-008", "other", "Lower my margin?", "Margin change request.")
    CASES.clear()  # what a restarted app would see
    saved = list_cases("M-003")
    assert [c["case_id"] for c in saved] == [second.case_id, first.case_id]
    assert saved[0]["margin_snapshot"]["status"] == "below_mm"
    assert len(list_cases()) == 3
