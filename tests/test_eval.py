"""OWNER: B. Eval scoring on hand-made responses, so no API calls."""
import json

from agent.tools import run_tool
from contracts import AgentResponse
from eval.run_eval import score, summarize, unfaithful_numbers


def _response(answer, *calls, citations=(), escalate=False):
    tools_called = [{"name": n, "input": a, "output": run_tool(n, a, "M-003"), "is_error": False} for n, a in calls]
    return AgentResponse(answer, list(citations), tools_called, escalate, None)


STATUS = ("margin_status", {})


def test_engine_numbers_pass_at_any_precision():
    answer = "Your equity is $1,137.40 against a maintenance requirement of 1,241.22, about 1,137 vs 1,241."
    assert unfaithful_numbers(_response(answer, STATUS), "Am I at risk?") == []


def test_made_up_number_is_flagged():
    answer = "Your equity is $1,137.40 but you need 1,500.00 to be safe."
    assert unfaithful_numbers(_response(answer, STATUS), "Am I at risk?") == ["1,500.00"]


def test_number_without_any_tool_call_is_flagged():
    assert unfaithful_numbers(_response("Your equity is 1,137.40."), "Am I at risk?") == ["1,137.40"]


def test_ratios_may_be_quoted_as_percentages():
    answer = "NVDA's maintenance ratio is 30% and its soft edge is 20%."
    assert unfaithful_numbers(_response(answer, STATUS), "What are my ratios?") == []


def test_rule_text_dates_question_numbers_and_urls_are_skipped():
    answer = (
        "If it stays below for 48 hours, on 6 Nov 2026 we may sell. An 8% drop is what you asked about. "
        "See https://www.moomoo.com/sg/support/topic5_493"
    )
    assert unfaithful_numbers(_response(answer), "It's Friday. If NVDA drops 8%, what happens?") == []


def test_help_centre_example_numbers_count_as_sources():
    search = ("search_help_centre", {"query": "worked example of the soft edge margin requirement when market value drops"})
    response = _response("In moomoo's example, a 10,000 position needs 3,000 of maintenance.", search)
    numbers_in_chunks = " ".join(c["text"] for c in json.loads(response.tools_called[0]["output"]))
    assert "10,000" in numbers_in_chunks  # the example this test relies on was retrieved
    assert unfaithful_numbers(response, "Show me an example") == []


def test_score_includes_numeric_check():
    q = {"question": "Am I at risk?", "expect_tools": ["margin_status"], "expect_escalation": False,
         "must_mention": ["maintenance"], "must_not": []}
    good = score(q, _response("Equity 1,137.40 is below maintenance 1,241.22.", STATUS))
    bad = score(q, _response("Equity 1,200.00 is below maintenance 1,241.22.", STATUS))
    assert good["pass"] and good["numbers_faithful"]
    assert not bad["pass"] and bad["unsupported_numbers"] == ["1,200.00"]


def test_summary_table_has_a_row_per_category_and_a_total():
    rows = [
        {"category": "concept", "pass": True, **dict.fromkeys(["tools_used", "escalation", "mentions", "no_forbidden", "citation", "numbers_faithful"], True)},
        {"category": "account", "pass": False, **dict.fromkeys(["tools_used", "escalation", "mentions", "no_forbidden", "citation"], True), "numbers_faithful": False},
    ]
    table = summarize(rows)
    assert "| concept | 1 | 1/1 |" in table
    assert "| account | 1 | 0/1 |" in table
    assert "| **total** | 2 | 1/2 |" in table
