"""Run eval/questions.jsonl through the agent and score it. OWNER: B.

Usage: python -m eval.run_eval              (all 30 questions; calls the API, so it costs money)
       python -m eval.run_eval c01 a05      (only these question ids)
Writes eval/results/<timestamp>.jsonl (every answer) and .md (pass rates by category).
"""
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agent.agent import respond
from agent.faithfulness import unfaithful_numbers
from contracts import AgentResponse

ROOT = Path(__file__).parent
CHECKS = ["tools_used", "escalation", "mentions", "no_forbidden", "citation", "numbers_faithful"]

def score(q: dict, response: AgentResponse) -> dict:
    used = {c["name"] for c in response.tools_called}
    low = response.answer.lower()
    unsupported = unfaithful_numbers(response, q["question"])
    checks = {
        "tools_used": all(t in used for t in q["expect_tools"]),
        "escalation": response.escalate == q["expect_escalation"],
        "mentions": all(m.lower() in low for m in q["must_mention"]),
        "no_forbidden": not any(m.lower() in low for m in q["must_not"]),
        "citation": "expect_url" not in q or q["expect_url"] in [c["url"] for c in response.citations],
        "numbers_faithful": not unsupported,
    }
    return {**checks, "pass": all(checks.values()), "unsupported_numbers": unsupported}


def summarize(rows: list[dict]) -> str:
    """Markdown table of pass rates by category, with a total row."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    groups["**total**"] = rows
    lines = [
        "| Category | n | Pass | " + " | ".join(CHECKS) + " |",
        "|---|---|---|" + "---|" * len(CHECKS),
    ]
    for category, group in groups.items():
        rate = lambda key: f"{sum(r[key] for r in group)}/{len(group)}"  # noqa: E731
        lines.append(f"| {category} | {len(group)} | {rate('pass')} | " + " | ".join(rate(c) for c in CHECKS) + " |")
    return "\n".join(lines)


def main(ids: list[str]):
    """Each answer is saved as soon as it arrives, so a crash (e.g. no API credit) keeps the
    answers so far and still prints their summary."""
    questions = [json.loads(l) for l in (ROOT / "questions.jsonl").read_text().splitlines() if l.strip()]
    if ids:
        questions = [q for q in questions if q["id"] in ids]
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    rows = []
    try:
        with (ROOT / "results" / f"{stamp}.jsonl").open("w") as out:
            for q in questions:
                response = respond([{"role": "user", "content": q["question"]}], q["account_id"])
                rows.append({
                    "id": q["id"],
                    "category": q["category"],
                    "reply": response.answer,
                    "tools_called": [c["name"] for c in response.tools_called],
                    **score(q, response),
                })
                out.write(json.dumps(rows[-1]) + "\n")
                out.flush()
                failed = [c for c in CHECKS if not rows[-1][c]]
                print(f"{q['id']}: {'PASS' if rows[-1]['pass'] else 'FAIL ' + ', '.join(failed)}")
    finally:
        if rows:
            table = summarize(rows)
            if len(rows) < len(questions):
                table += f"\n\nStopped after {len(rows)} of {len(questions)} questions."
            (ROOT / "results" / f"{stamp}.md").write_text(table + "\n")
            print(table)


if __name__ == "__main__":
    load_dotenv()
    main(sys.argv[1:])
