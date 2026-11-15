"""
Pytest configuration for DiffGuard backend test suite.
Ensures unit and integration tests run deterministically offline without making
unintended upstream LLM network calls or burning API quotas.
"""

import pytest
from app.config import settings


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """
    Ensures tests default to offline deterministic execution by default.
    Specific tests that verify API key presence can override this fixture.
    """
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
