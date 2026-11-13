"""
Integration tests for FastAPI REST and SSE endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH, SAMPLE_CLEAN_PR

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_list_samples_endpoint():
    res = client.get("/api/samples")
    assert res.status_code == 200
    samples = res.json()
    assert len(samples) >= 5
    assert any(s["id"] == "sample-sqli-auth" for s in samples)


def test_get_single_sample_endpoint():
    res = client.get("/api/samples/sample-sqli-auth")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "sample-sqli-auth"
    assert "diff_content" in data


def test_get_nonexistent_sample_returns_404():
    res = client.get("/api/samples/does-not-exist")
    assert res.status_code == 404


def test_review_endpoint_empty_diff_returns_400():
    res = client.post("/api/review", json={"diff_content": "   "})
    assert res.status_code in (400, 422)


def test_review_endpoint_valid_sqli():
    res = client.post(
        "/api/review",
        json={"diff_content": SAMPLE_SQLI_AUTH.diff_content, "title": "Test SQL Injection PR"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "review_id" in data
    assert len(data["findings"]) >= 1
    assert data["summary"]["total_findings"] >= 1
    assert len(data["stages_executed"]) >= 3


def test_review_endpoint_clean_pr():
    res = client.post(
        "/api/review",
        json={"diff_content": SAMPLE_CLEAN_PR.diff_content, "title": "Test Clean PR"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["verdict"] in ("APPROVED", "APPROVED_WITH_COMMENTS")

