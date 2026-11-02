"""Claude tool-use loop. OWNER: C."""
from __future__ import annotations

import os

import anthropic

from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOLS, run_tool

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
MAX_TURNS = 10

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def chat(messages: list[dict], account_id: str) -> tuple[str, list[dict]]:
    """Run one customer turn. `messages` is the full history (mutated in place).

    Returns (reply_text, tool_calls) where tool_calls is a log for the UI/eval:
    [{"name", "input", "output", "is_error"}].
    """
    client = _get_client()
    tool_calls: list[dict] = []

    for _ in range(MAX_TURNS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "medium"},
            # On a safety-classifier decline, the API retries on a fallback model in the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        # Append the full content (incl. thinking blocks) so the history stays valid.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            return "Sorry, I can't help with that. Let me connect you to our support team.", tool_calls
        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            return text, tool_calls

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
        messages.append({"role": "user", "content": results})

    return "Sorry, this is taking too long. Please try again or contact support.", tool_calls
