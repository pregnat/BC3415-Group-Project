"""Claude tool-use loop. OWNER: C."""
from __future__ import annotations

import json
import os

import anthropic

from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOLS, run_tool
from contracts import AgentResponse

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
MAX_TURNS = 10

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def _build_response(answer: str, tool_calls: list[dict]) -> AgentResponse:
    """Citations are the retrieved chunks whose URL the answer actually quotes."""
    citations: dict[str, dict[str, str]] = {}
    case_summary = None
    for call in tool_calls:
        if call["is_error"]:
            continue
        if call["name"] == "search_help_centre":
            for chunk in json.loads(call["output"]):
                if chunk["url"] in answer:
                    citations.setdefault(
                        chunk["url"], {"chunk_id": chunk["chunk_id"], "title": chunk["title"], "url": chunk["url"]}
                    )
        elif call["name"] == "escalate_to_risk_desk":
            case_summary = json.loads(call["output"])
    return AgentResponse(
        answer=answer,
        citations=list(citations.values()),
        tools_called=tool_calls,
        escalate=case_summary is not None,
        case_summary=case_summary,
    )


def respond(history: list[dict], account_id: str) -> AgentResponse:
    """Run one customer turn. `history` is the full message list (mutated in place)."""
    client = _get_client()
    tool_calls: list[dict] = []

    for _ in range(MAX_TURNS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
            output_config={"effort": "medium"},
            # On a safety-classifier decline, the API retries on a fallback model in the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        # Append the full content (incl. thinking blocks) so the history stays valid.
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            return _build_response("Sorry, I can't help with that. Let me connect you to our support team.", tool_calls)
        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            return _build_response(text, tool_calls)

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                output, is_error = run_tool(block.name, block.input, account_id), False
            except Exception as e:  # report tool failures to the model instead of crashing
                output, is_error = f"Error: {e}", True
            tool_calls.append({"name": block.name, "input": block.input, "output": output, "is_error": is_error})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error})
        history.append({"role": "user", "content": results})

    return _build_response("Sorry, this is taking too long. Please try again or contact support.", tool_calls)
