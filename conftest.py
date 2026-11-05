# Lets pytest import top-level packages (contracts, engine, rag, agent) from the repo root.
import pytest


@pytest.fixture(autouse=True)
def _cases_db(tmp_path, monkeypatch):
    """Escalation cases created by tests go to a throwaway database, not data/cases.db."""
    monkeypatch.setattr("agent.escalation.CASES_DB", tmp_path / "cases.db")
