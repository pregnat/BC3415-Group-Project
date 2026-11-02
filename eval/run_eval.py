"""Run eval/questions.jsonl through the agent and score it. OWNER: B.

Usage: python -m eval.run_eval
"""
import json
from datetime import datetime
from pathlib import Path

from agent.agent import respond
from contracts import AgentResponse

ROOT = Path(__file__).parent


def score(q: dict, response: AgentResponse) -> dict:
    used = {c["name"] for c in response.tools_called}
    low = response.answer.lower()
    checks = {
        "tools_used": all(t in used for t in q["expect_tools"]),
        "escalation": response.escalate == q["expect_escalation"],
        "mentions": all(m.lower() in low for m in q["must_mention"]),
        "no_forbidden": not any(m.lower() in low for m in q["must_not"]),
        "citation": "expect_url" not in q or q["expect_url"] in [c["url"] for c in response.citations],
    }
    # TODO(B): add numeric check (numbers in reply match margin_status output).
    return {**checks, "pass": all(checks.values())}


def main():
    questions = [json.loads(l) for l in (ROOT / "questions.jsonl").read_text().splitlines() if l.strip()]
    rows = []
    for q in questions:
        response = respond([{"role": "user", "content": q["question"]}], q["account_id"])
        rows.append({"id": q["id"], "category": q["category"], "reply": response.answer, **score(q, response)})
        print(f"{q['id']}: {'PASS' if rows[-1]['pass'] else 'FAIL'}")
    out = ROOT / "results" / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows))
    print(f"{sum(r['pass'] for r in rows)}/{len(rows)} passed -> {out}")


if __name__ == "__main__":
    main()
