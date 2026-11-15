"""
Integration tests for Engineering Standards Engine review pipeline.
Verifies:
- ReviewRequest with custom standards_yaml evaluates policies.
- ReviewSummary accurately separates total_defects vs total_policy_violations.
- Fallback engine incorporates policy findings with verified location.
- Standalone endpoints (/api/standards/default and /api/standards/validate).
- Malformed standards_yaml returns HTTP 400.
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app.main import app
from app.agent.reviewer_agent import ReviewAgent
from app.models.schemas import ReviewRequest, FindingType, SeverityLevel, ReviewSummary
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH

client = TestClient(app)


SAMPLE_PROHIBITED_IMPORT_DIFF = """diff --git a/services/auth.py b/services/auth.py
index 1000000..2000000 100644
--- a/services/auth.py
+++ b/services/auth.py
@@ -1,3 +1,5 @@
+import pickle
 def login(user):
+    return pickle.loads(user)
"""

VALID_STANDARDS_YAML = """
version: 1
project:
  name: test-project
standards:
  security:
    prohibited_imports:
      enabled: true
      values:
        - pickle
      severity: critical
    custom_patterns:
      enabled: true
      rules:
        - id: POLICY-AUTH-001
          name: Prohibited Pickle Loads
          pattern: 'pickle\\.loads'
          severity: high
"""


def test_standards_default_endpoint():
    """GET /api/standards/default returns valid default configuration structure."""
    res = client.get("/api/standards/default")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "default_config" in data
    assert "rules_status" in data
    assert data["default_config"]["version"] == 1


def test_standards_validate_endpoint_valid():
    """POST /api/standards/validate accepts valid YAML and returns active rules count."""
    res = client.post("/api/standards/validate", json={"standards_yaml": VALID_STANDARDS_YAML})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["project"] == "test-project"
    assert data["active_rules_count"] == 2


def test_standards_validate_endpoint_invalid_yaml():
    """POST /api/standards/validate returns 400 on malformed YAML."""
    res = client.post("/api/standards/validate", json={"standards_yaml": "version: [unclosed"})
    assert res.status_code == 400
    assert "Malformed YAML" in res.json()["detail"]


def test_standards_validate_endpoint_invalid_schema():
    """POST /api/standards/validate returns 400 on schema violation (e.g. unknown keys)."""
    bad_yaml = "version: 1\nillegal_key: 123"
    res = client.post("/api/standards/validate", json={"standards_yaml": bad_yaml})
    assert res.status_code == 400
    assert "Invalid .diffguard.yaml" in res.json()["detail"]


def test_pipeline_evaluates_standards_and_separates_defects_and_policies():
    """Verify that ReviewResponse separates total_defects from total_policy_violations."""
    payload = {
        "diff_content": SAMPLE_PROHIBITED_IMPORT_DIFF,
        "standards_yaml": VALID_STANDARDS_YAML
    }
    res = client.post("/api/review", json=payload)
    assert res.status_code == 200
    data = res.json()

    findings = data["findings"]
    summary = data["summary"]

    # Verify policy findings exist
    policy_findings = [f for f in findings if f.get("finding_type") == "policy_violation"]
    assert len(policy_findings) >= 2  # prohibited_imports and custom_patterns

    # Verify summary counters
    assert summary["total_policy_violations"] >= 2
    assert "policy_violation" in summary["by_finding_type"]
    assert summary["total_findings"] == summary["total_defects"] + summary["total_policy_violations"] + summary["total_recommendations"]

    # Verify rule IDs and locations are verified
    rule_ids = {f.get("rule_id") for f in policy_findings}
    assert "STD-IMP-001" in rule_ids
    assert "POLICY-AUTH-001" in rule_ids
    for pf in policy_findings:
        assert pf["location"]["location_status"] in ("verified", "file_level")


def test_malformed_standards_in_review_endpoint_returns_400():
    """Submitting malformed standards_yaml to /api/review halts with HTTP 400."""
    payload = {
        "diff_content": SAMPLE_PROHIBITED_IMPORT_DIFF,
        "standards_yaml": "version: 1\nstandards: {bad: yaml:"
    }
    res = client.post("/api/review", json=payload)
    assert res.status_code == 400
    assert "Malformed YAML" in res.json()["detail"]


def test_gemini_mode_merges_deterministic_policy_findings():
    """In agent mode with mocked Gemini, deterministic policy findings are preserved alongside Gemini findings."""
    mock_client = MagicMock()
    # Mock Gemini returning 1 code defect
    gemini_finding = {
        "id": "DG-001",
        "title": "Raw SQL injection",
        "category": "SECURITY_AND_RELIABILITY",
        "severity": "CRITICAL",
        "confidence": "CONFIRMED_ISSUE",
        "finding_type": "code_defect",
        "location": {
            "file_path": "services/auth.py",
            "start_line": 2,
            "line_side": "new"
        },
        "why_identified": "SQL injection vulnerability.",
        "impact": "Data breach.",
        "suggested_fix": {"description": "Fix SQL query."}
    }
    mock_candidate_text = {
        "review_id": "REV-MOCK-01",
        "timestamp": "2026-11-14T00:00:00Z",
        "parsed_files_count": 1,
        "total_additions": 2,
        "total_deletions": 0,
        "summary": {
            "total_findings": 1,
            "total_defects": 1,
            "total_policy_violations": 0,
            "total_recommendations": 0,
            "verdict": "CRITICAL_BLOCKER",
            "key_takeaways": ["Critical issue found."]
        },
        "findings": [gemini_finding],
        "stages_executed": [],
        "engine_used": "gemini-agent"
    }
    import json
    part_synth = types.Part.from_text(text=json.dumps(mock_candidate_text))
    cand_synth = types.Candidate(content=types.Content(role="model", parts=[part_synth]))
    resp_synth = types.GenerateContentResponse(candidates=[cand_synth])

    part_concl = types.Part.from_text(text="Investigation finished.")
    cand_concl = types.Candidate(content=types.Content(role="model", parts=[part_concl]))
    resp_concl = types.GenerateContentResponse(candidates=[cand_concl])

    mock_client.models.generate_content.side_effect = [resp_concl, resp_synth]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(
        diff_content=SAMPLE_PROHIBITED_IMPORT_DIFF,
        standards_yaml=VALID_STANDARDS_YAML
    )
    result = agent.execute_review(req)

    # Gemini defect is present
    defect_findings = [f for f in result.findings if f.finding_type == FindingType.CODE_DEFECT]
    assert len(defect_findings) == 1
    assert defect_findings[0].id == "DG-001"

    # Deterministic policy violations were merged and NOT discarded by the model
    policy_findings = [f for f in result.findings if f.finding_type == FindingType.POLICY_VIOLATION]
    assert len(policy_findings) >= 2
    assert result.summary.total_defects == 1
    assert result.summary.total_policy_violations == len(policy_findings)
