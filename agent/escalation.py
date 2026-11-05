"""Hand-off to the human risk desk. OWNER: C.

Cases are saved to SQLite (data/cases.db, or $CASES_DB) so they survive an app restart. Streamlit
Community Cloud wipes the disk when the app redeploys, so this is a demo store, not a real queue.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from contracts import EscalationCase, EscalationReason
from engine.margin import margin_status

CASES_DB = Path(os.getenv("CASES_DB", Path(__file__).resolve().parents[1] / "data" / "cases.db"))
CASES: dict[str, EscalationCase] = {}  # cases created by this process


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(CASES_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cases ("
        "case_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, created_at TEXT NOT NULL, case_json TEXT NOT NULL)"
    )
    return conn


def create_case(
    account_id: str,
    reason: EscalationReason,
    customer_message: str,
    summary: str,
    timeline: list[str] | None = None,
    rule_cited: str = "",
    cited_chunk_ids: list[str] | None = None,
) -> EscalationCase:
    case = EscalationCase(
        case_id=f"RISK-{uuid.uuid4().hex[:8].upper()}",
        account_id=account_id,
        reason=reason,
        customer_message=customer_message,
        summary=summary,
        timeline=timeline or [],
        rule_cited=rule_cited,
        margin_snapshot=margin_status(account_id),
        cited_chunk_ids=cited_chunk_ids or [],
        created_at=datetime.now(),
    )
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO cases VALUES (?, ?, ?, ?)",
            (case.case_id, account_id, case.created_at.isoformat(), json.dumps(asdict(case), default=str)),
        )
    CASES[case.case_id] = case
    return case


def list_cases(account_id: str | None = None) -> list[dict]:
    """Saved cases as JSON dicts, newest first, optionally for one account."""
    query, params = "SELECT case_json FROM cases", ()
    if account_id:
        query, params = query + " WHERE account_id = ?", (account_id,)
    with closing(_connect()) as conn:
        rows = conn.execute(query + " ORDER BY created_at DESC", params).fetchall()
    return [json.loads(row[0]) for row in rows]
