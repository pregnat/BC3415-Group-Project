"""Checks that every figure in an answer came from a tool, so hallucinated numbers are caught.
Used live by the app (a badge under each answer) and by eval/run_eval.py. OWNER: B."""
from __future__ import annotations

import json
import re

from contracts import AgentResponse

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
