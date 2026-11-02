"""Hand-off to the human risk desk. OWNER: C."""
from __future__ import annotations

import uuid
from datetime import datetime

from contracts import EscalationCase, EscalationReason
from engine.margin import compute_margin_status

CASES: dict[str, EscalationCase] = {}  # TODO(C): persist (sqlite table in accounts.db?)


def create_case(
    account_id: str,
    reason: EscalationReason,
    customer_message: str,
    summary: str,
    cited_chunk_ids: list[str] | None = None,
) -> EscalationCase:
    case = EscalationCase(
        case_id=f"RISK-{uuid.uuid4().hex[:8].upper()}",
        account_id=account_id,
        reason=reason,
        customer_message=customer_message,
        summary=summary,
        margin_snapshot=compute_margin_status(account_id),
        cited_chunk_ids=cited_chunk_ids or [],
        created_at=datetime.now(),
    )
    CASES[case.case_id] = case
    return case
