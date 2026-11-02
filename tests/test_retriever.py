"""OWNER: B. Retrieval quality checks. No API calls; the first run builds the local index."""
import json
from pathlib import Path

import pytest

from rag.retriever import retrieve, search

QUESTIONS = [json.loads(l) for l in (Path(__file__).parents[1] / "eval" / "questions.jsonl").read_text().splitlines() if l.strip()]
CONCEPT = [q for q in QUESTIONS if q["category"] == "concept"]


@pytest.mark.parametrize("q", CONCEPT, ids=[q["id"] for q in CONCEPT])
def test_concept_question_finds_expected_page(q):
    assert q["expect_url"] in [h["url"] for h in retrieve(q["question"])]


@pytest.mark.parametrize("query,expected_text", [
    ("What's the difference between maintenance and soft-edge margin?", "forced liquidation may occur immediately"),
    ("what happens if I stay below maintenance margin for 2 days", "more than 48 hours"),
    ("when is the soft edge margin raised before a weekend", "raised on the day before a weekend"),
])
def test_rule_text_is_retrieved(query, expected_text):
    assert any(expected_text in h["text"] for h in retrieve(query))


def test_hit_has_plan_fields():
    hit = retrieve("what is soft edge margin", k=1)[0]
    assert {"text", "title", "url", "date", "product", "score"} <= hit.keys()
    assert hit["url"].startswith("https://www.moomoo.com/sg/support/topic5_")


def test_product_filter_excludes_conflicting_rules():
    query = "force-liquidation margin close-out level"
    assert all(h["product"] == "securities_margin" for h in retrieve(query))
    assert {h["product"] for h in retrieve(query, product="forex_cfd")} == {"forex_cfd"}
    assert not any("topic5_607" in h["chunk_id"] or "topic5_150" in h["chunk_id"] for h in retrieve(query))


@pytest.mark.parametrize("query", ["what is the best sourdough recipe", "what is the capital of France"])
def test_off_topic_returns_nothing(query):
    assert retrieve(query) == []


def test_unknown_product_returns_nothing():
    assert retrieve("soft edge margin", product="no_such_product") == []


def test_search_keeps_contract_shape():
    chunks = search("what is soft edge margin", k=2)
    assert len(chunks) == 2 and all(c.chunk_id and c.url for c in chunks)
