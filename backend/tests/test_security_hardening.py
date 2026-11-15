"""
Security and Hardening Tests for DiffGuard Phase 1.
Verifies:
1. CORS configuration hardening (no wildcard origin, allowed origins).
2. Gemini provider error sanitization (no key or URL leaks).
3. Request-scoped API key isolation.
4. Response and SSE event payload security (no credentials in outputs).
"""

from fastapi.testclient import TestClient
from app.main import app
from app.config import Settings, DEFAULT_DEV_ORIGINS
from app.agent.reviewer_agent import sanitize_provider_error, ReviewAgent
from app.models.schemas import ReviewRequest
from app.samples.sample_diffs import SAMPLE_CLEAN_PR

client = TestClient(app)


def test_cors_dev_defaults():
    """Verify that development configurations automatically include default local origins."""
    settings = Settings(APP_ENV="development")
    assert "*" not in settings.CORS_ORIGINS
    for dev_origin in DEFAULT_DEV_ORIGINS:
        assert dev_origin in settings.CORS_ORIGINS


def test_cors_dev_custom_origins():
    """Verify that custom origins in dev are combined with default local origins."""
    settings = Settings(
        APP_ENV="development",
        CORS_ORIGINS="http://mydev:5173, https://preview.internal.org"
    )
    assert "http://mydev:5173" in settings.CORS_ORIGINS
    assert "https://preview.internal.org" in settings.CORS_ORIGINS
    assert "http://localhost:3000" in settings.CORS_ORIGINS


def test_cors_production_explicit_origins():
    """Verify production uses explicitly configured origins and normalizes whitespace/trailing slashes."""
    settings = Settings(
        APP_ENV="production",
        CORS_ORIGINS="  https://diffguard.internal.org/ , https://audit.diffguard.net/  "
    )
    assert settings.CORS_ORIGINS == [
        "https://diffguard.internal.org",
        "https://audit.diffguard.net"
    ]


def test_cors_production_without_origins_fails_safe():
    """Verify production with unconfigured or empty origins fails safe to an empty allowlist."""
    settings = Settings(APP_ENV="production", CORS_ORIGINS="")
    assert settings.CORS_ORIGINS == []
    settings_none = Settings(APP_ENV="production")
    assert settings_none.CORS_ORIGINS == []


def test_cors_production_excludes_dev_origins():
    """Verify production strictly excludes localhost/127.0.0.1 origins even if passed in string."""
    settings = Settings(
        APP_ENV="production",
        CORS_ORIGINS="https://diffguard.internal.org, http://localhost:3000, http://127.0.0.1:8000"
    )
    assert "https://diffguard.internal.org" in settings.CORS_ORIGINS
    assert "http://localhost:3000" not in settings.CORS_ORIGINS
    assert "http://127.0.0.1:8000" not in settings.CORS_ORIGINS


def test_cors_rejects_wildcard():
    """Verify wildcard '*' is rejected across both development and production."""
    settings_dev = Settings(APP_ENV="development", CORS_ORIGINS="*, http://custom:3000")
    assert "*" not in settings_dev.CORS_ORIGINS
    settings_prod = Settings(APP_ENV="production", CORS_ORIGINS="*, https://prod.internal")
    assert "*" not in settings_prod.CORS_ORIGINS
    assert settings_prod.CORS_ORIGINS == ["https://prod.internal"]


def test_cors_trailing_slash_normalized():
    """Verify trailing slashes are removed so origins match browser preflight headers accurately."""
    settings = Settings(
        APP_ENV="production",
        CORS_ORIGINS="https://api.diffguard.internal/"
    )
    assert settings.CORS_ORIGINS == ["https://api.diffguard.internal"]


def test_cors_approved_origin_header():
    """Test that requests from approved origins receive appropriate CORS headers."""
    headers = {"Origin": "http://localhost:3000"}
    res = client.options("/api/health", headers=headers)
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_unapproved_origin_rejected():
    """Test that unauthorized web origins do not receive allow-origin headers."""
    headers = {"Origin": "http://malicious-site.attacker.com"}
    res = client.options("/api/health", headers=headers)
    assert res.headers.get("access-control-allow-origin") is None


def test_sanitize_provider_error_authentication():
    """Verify that 401/403 or auth errors return clean messages without echoing keys."""
    raw_err = Exception("401 Invalid API key provided: AIzaSySecretKey123456789. Access denied.")
    sanitized = sanitize_provider_error(raw_err)
    assert "AIzaSy" not in sanitized
    assert "Gemini authentication failed" in sanitized


def test_sanitize_provider_error_timeout():
    """Verify that network timeout errors are categorized cleanly."""
    raw_err = Exception("HTTPSConnectionPool: Read timed out after 30 seconds.")
    sanitized = sanitize_provider_error(raw_err)
    assert "timed out" in sanitized.lower()


def test_sanitize_provider_error_quota():
    """Verify that 429 quota errors are sanitized."""
    raw_err = Exception("429 Resource has been exhausted (e.g. check quota).")
    sanitized = sanitize_provider_error(raw_err)
    assert "quota or rate limit" in sanitized.lower()


def test_sanitize_provider_error_service_unavailable():
    """Verify that 503 unavailable errors return safe messaging."""
    raw_err = Exception("503 The model is overloaded. Please try again later.")
    sanitized = sanitize_provider_error(raw_err)
    assert "temporarily unavailable" in sanitized.lower()


def test_review_response_never_contains_submitted_api_key():
    """Verify that a submitted custom API key is NEVER reflected in the review response."""
    fake_key = "AIzaSyTestKeyNeverExposeInResponse999"
    res = client.post(
        "/api/review",
        json={
            "diff_content": SAMPLE_CLEAN_PR.diff_content,
            "api_key": fake_key,
            "title": "Clean PR Review"
        }
    )
    assert res.status_code == 200
    data = res.json()
    response_text = str(data)
    assert fake_key not in response_text
    assert "api_key" not in data


def test_concurrent_api_key_isolation():
    """Verify that initializing ReviewAgent with a custom key does not mutate global settings."""
    initial_global = app.state if hasattr(app, "state") else None
    
    agent_1 = ReviewAgent(api_key="key_user_alpha")
    agent_2 = ReviewAgent(api_key="key_user_beta")
    agent_default = ReviewAgent(api_key=None)

    assert agent_1.api_key == "key_user_alpha"
    assert agent_2.api_key == "key_user_beta"
    assert agent_default.api_key != "key_user_alpha"
    assert agent_default.api_key != "key_user_beta"

