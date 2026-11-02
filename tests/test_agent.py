"""OWNER: C. The agent loop against a fake client, so no API calls."""
from types import SimpleNamespace

import agent.agent as agent_module
from contracts import AgentResponse


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _tool(name, args):
    return SimpleNamespace(type="tool_use", name=name, input=args, id=f"tool_{name}")


def _fake_client(monkeypatch, *replies):
    queue = list(replies)

    def create(**_):
        content, stop_reason = queue.pop(0)
        return SimpleNamespace(content=content, stop_reason=stop_reason)

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(agent_module, "_get_client", lambda: client)


def test_plain_answer(monkeypatch):
    _fake_client(monkeypatch, ([_text("Hello")], "end_turn"))
    response = agent_module.respond([{"role": "user", "content": "hi"}], "M-003")
    assert isinstance(response, AgentResponse)
    assert (response.answer, response.citations, response.escalate, response.case_summary) == ("Hello", [], False, None)


def test_citation_only_if_answer_quotes_the_url(monkeypatch):
    url = "https://www.moomoo.com/sg/support/topic5_493"
    _fake_client(
        monkeypatch,
        ([_tool("search_help_centre", {"query": "what is soft edge margin"})], "tool_use"),
        ([_text(f"See {url}")], "end_turn"),
    )
    response = agent_module.respond([{"role": "user", "content": "soft edge?"}], "M-003")
    assert [c["url"] for c in response.citations] == [url]
    assert response.tools_called[0]["name"] == "search_help_centre"


def test_escalation_sets_flag_and_case(monkeypatch):
    args = {
        "reason": "liquidation_dispute",
        "customer_message": "I want compensation.",
        "summary": "Dispute.",
        "timeline": [],
        "rule_cited": "Soft edge rule.",
        "cited_chunk_ids": [],
    }
    _fake_client(
        monkeypatch,
        ([_tool("escalate_to_risk_desk", args)], "tool_use"),
        ([_text("Your case is open.")], "end_turn"),
    )
    response = agent_module.respond([{"role": "user", "content": "compensate me"}], "M-003")
    assert response.escalate
    assert response.case_summary["case_id"].startswith("RISK-")
    assert response.case_summary["margin_snapshot"]["status"] == "below_mm"


def test_tool_error_goes_back_to_the_model(monkeypatch):
    _fake_client(
        monkeypatch,
        ([_tool("get_prices", {"tickers": ["NOPE"]})], "tool_use"),
        ([_text("I couldn't find that ticker.")], "end_turn"),
    )
    response = agent_module.respond([{"role": "user", "content": "price of NOPE?"}], "M-003")
    assert response.tools_called[0]["is_error"]
    assert response.answer == "I couldn't find that ticker."
