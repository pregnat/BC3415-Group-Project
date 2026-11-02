"""OWNER: C."""
from agent.escalation import CASES, create_case


def test_case_created_with_snapshot():
    case = create_case("ACC-001", "liquidation_dispute", "You sold my shares!", "Dispute re: liquidation.")
    assert case.case_id.startswith("RISK-")
    assert case.margin_snapshot is not None
    assert CASES[case.case_id] is case
