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


def test_engine_gaps_can_be_quoted():
    """The a06 and c03 failures: 309.92 above soft edge is now an engine number."""
    answer = "Your equity is 309.92 above the soft edge requirement of 827.48."
    assert unfaithful_numbers(_response(answer, STATUS), "How far am I from the soft edge?") == []


def test_agent_arithmetic_rounding_error_is_still_caught():
    """The a05 answer said 335.52; the engine's gap is 335.5144, so only 335.51 is faithful."""
    shocks = {"shocks": [{"ticker": "NVDA", "pct_change": -0.08}]}
    response = _response("You'd be 335.52 short of the raised soft edge.", ("weekend_risk_check", shocks))
    assert unfaithful_numbers(response, "It's Friday. If NVDA drops 8%, what happens?") == ["335.52"]
    response = _response("You'd be 335.51 short of the raised soft edge.", ("weekend_risk_check", shocks))
    assert unfaithful_numbers(response, "It's Friday. If NVDA drops 8%, what happens?") == []


def test_example_percentages_in_an_offer_are_not_account_figures():
    """The v03 and v05 refusals offered 'what if NVDA falls 10%' with no tool call."""
    answer = "I can't predict prices, but I can show what happens if NVDA falls 10%."
    assert unfaithful_numbers(_response(answer), "Is NVDA going to go up next week?") == []


def test_wrong_drop_percentage_is_still_caught():
    response = _response("NVDA can fall 12.5% before you reach the soft edge.", ("liquidation_distance", {"shocks": []}))
    assert unfaithful_numbers(response, "How far can NVDA fall?") == ["12.5%"]


def test_a_crash_keeps_the_answers_so_far(tmp_path, monkeypatch):
    import eval.run_eval as run_eval

    calls = []

    def fake_respond(history, account_id):
        calls.append(account_id)
        if len(calls) == 3:
            raise RuntimeError("credit balance is too low")
        return AgentResponse("I can't give advice.", [], [], False, None)

    (tmp_path / "results").mkdir()
    monkeypatch.setattr(run_eval, "ROOT", tmp_path)
    (tmp_path / "questions.jsonl").write_text("\n".join(json.dumps({
        "id": f"v0{i}", "account_id": "M-001", "question": "Should I buy?", "category": "advice_refusal",
        "expect_tools": [], "expect_escalation": False, "must_mention": [], "must_not": ["I recommend"],
    }) for i in range(1, 5)))
    monkeypatch.setattr(run_eval, "respond", fake_respond)
    try:
        run_eval.main([])
    except RuntimeError:
        pass
    saved = [json.loads(l) for l in next(tmp_path.glob("results/*.jsonl")).read_text().splitlines()]
    assert [r["id"] for r in saved] == ["v01", "v02"]
    assert "Stopped after 2 of 4 questions." in next(tmp_path.glob("results/*.md")).read_text()
