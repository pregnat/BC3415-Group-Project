"""Run eval/questions.jsonl through the agent and score it. OWNER: B.

Usage: python -m eval.run_eval
"""
import json
from datetime import datetime
from pathlib import Path

from agent.agent import chat

ROOT = Path(__file__).parent


def score(q: dict, reply: str, tool_calls: list[dict]) -> dict:
    used = {c["name"] for c in tool_calls}
    low = reply.lower()
    checks = {
        "tools_used": all(t in used for t in q["expect_tools"]),
        "escalation": ("escalate_to_risk_desk" in used) == q["expect_escalation"],
        "mentions": all(m.lower() in low for m in q["must_mention"]),
        "no_forbidden": not any(m.lower() in low for m in q["must_not"]),
    }
    # TODO(B): add citation check (reply cites a url returned by search_help_centre)
    # and numeric check (numbers in reply match get_margin_status output).
    return {**checks, "pass": all(checks.values())}


def main():
    questions = [json.loads(l) for l in (ROOT / "questions.jsonl").read_text().splitlines() if l.strip()]
    rows = []
    for q in questions:
        reply, tool_calls = chat([{"role": "user", "content": q["question"]}], q["account_id"])
        rows.append({"id": q["id"], "category": q["category"], "reply": reply, **score(q, reply, tool_calls)})
        print(f"{q['id']}: {'PASS' if rows[-1]['pass'] else 'FAIL'}")
    out = ROOT / "results" / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows))
    print(f"{sum(r['pass'] for r in rows)}/{len(rows)} passed -> {out}")


if __name__ == "__main__":
    main()
