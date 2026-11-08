"""Run eval/questions.jsonl through the agent and score it. OWNER: B.

Usage: python -m eval.run_eval              (all 30 questions; calls the API, so it costs money)
       python -m eval.run_eval c01 a05      (only these question ids)
Writes eval/results/<timestamp>.jsonl (every answer) and .md (pass rates by category).
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agent.agent import respond
from contracts import AgentResponse

ROOT = Path(__file__).parent
CHECKS = ["tools_used", "escalation", "mentions", "no_forbidden", "citation", "numbers_faithful"]

_URL = re.compile(r"https?://\S+")
_NUMBER = re.compile(r"(?<![\w.])(\$?)(-?\d[\d,]*(?:\.\d+)?)(%?)")


def _numbers(text: str) -> list[tuple[float, int, bool, str]]:
    """(value, decimals, is_percent, as written) for each number in text, ignoring URLs."""
    found = []
    for dollar, digits, percent in _NUMBER.findall(_URL.sub(" ", text)):
        plain = digits.replace(",", "")
        decimals = len(plain.split(".")[1]) if "." in plain else 0
        found.append((float(plain), decimals, bool(percent), f"{dollar}{digits}{percent}"))
    return found


def _source_values(response: AgentResponse, question: str) -> list[float]:
    """Every number the agent was given: tool outputs (including help-centre text) and the question."""
    values: list[float] = []

    def walk(obj):
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            values.extend([float(obj), float(obj) * 100])  # ratios like 0.3 may be quoted as 30%
        elif isinstance(obj, str):
            values.extend(v for v, *_ in _numbers(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for call in response.tools_called:
        if not call["is_error"]:
            walk(json.loads(call["output"]))
    walk(question)
    return values


def unfaithful_numbers(response: AgentResponse, question: str) -> list[str]:
    """Numbers in the answer that no tool output or the question supports, at the precision the
    answer used ("1,137" matches 1137.4). Whole numbers up to 100, with or without % ("48 hours",
    "6 Nov", "if NVDA falls 10%") and years are skipped: they are rule text, dates and examples.
    Account figures have decimals or exceed 100, so they are still checked, as are "9.36%" drops."""
    sources = _source_values(response, question)
    bad = []
    for value, decimals, is_percent, written in _numbers(response.answer):
        is_small_int = decimals == 0 and "$" not in written and abs(value) <= 100
        if is_small_int or (decimals == 0 and 1900 <= value <= 2100):
            continue
        if not any(round(s, decimals) == round(value, decimals) for s in sources):
            bad.append(written)
    return bad


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
