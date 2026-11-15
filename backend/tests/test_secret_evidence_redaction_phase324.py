"""
Focused tests for Phase 3.2.4:
Secret Evidence Redaction & Disclosure Protection for SEC-SECRET-002.
All tests use synthetic credentials exclusively.
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tools.security_scanner import scan_security_issues
from app.agent.reviewer_agent import ReviewAgent
from app.models.schemas import ReviewRequest, LineSide, SeverityLevel
from app.samples.sample_diffs import SAMPLE_CLEAN_PR


SYNTHETIC_CREDENTIAL = "synthetic_secret_value_1234567890"


def _recursively_find_strings(data):
    """Helper to collect all string values in a nested JSON/dict/list structure."""
    strings = []
    if isinstance(data, dict):
        for v in data.values():
            strings.extend(_recursively_find_strings(v))
    elif isinstance(data, list):
        for item in data:
            strings.extend(_recursively_find_strings(item))
    elif isinstance(data, str):
        strings.append(data)
    return strings


class TestSecretEvidenceRedaction:
    """Category A & B: Core redaction & quoting formats."""

    def test_double_quoted_secret_is_redacted(self):
        raw_code = f'+ JWT_SECRET_KEY = "{SYNTHETIC_CREDENTIAL}"'
        findings = scan_security_issues(raw_code, "auth.py")

        assert len(findings) == 1
        finding = findings[0]
        assert finding["rule_id"] == "SEC-SECRET-002"
        assert "[REDACTED]" in finding["matched_code"]
        assert finding["matched_code"] == 'JWT_SECRET_KEY = "[REDACTED]"'
        assert SYNTHETIC_CREDENTIAL not in str(finding)

    def test_single_quoted_secret_is_redacted(self):
        raw_code = f"+ JWT_SECRET_KEY = '{SYNTHETIC_CREDENTIAL}'"
        findings = scan_security_issues(raw_code, "auth.py")

        assert len(findings) == 1
        finding = findings[0]
        assert finding["rule_id"] == "SEC-SECRET-002"
        assert "[REDACTED]" in finding["matched_code"]
        assert finding["matched_code"] == "JWT_SECRET_KEY = '[REDACTED]'"
        assert SYNTHETIC_CREDENTIAL not in str(finding)


class TestCompoundCredentialRedaction:
    """Category C: Compound credential identifiers."""

    @pytest.mark.parametrize("var_name", [
        "JWT_SECRET_KEY",
        "AWS_SECRET_KEY",
        "DATABASE_PASSWORD",
        "API_TOKEN",
        "PRIVATE_KEY"
    ])
    def test_compound_secret_values_are_redacted(self, var_name):
        raw_code = f'+ {var_name} = "{SYNTHETIC_CREDENTIAL}"'
        findings = scan_security_issues(raw_code, "config.py")

        assert len(findings) == 1
        finding = findings[0]
        assert finding["rule_id"] == "SEC-SECRET-002"
        assert var_name in finding["matched_code"]
        assert "[REDACTED]" in finding["matched_code"]
        assert SYNTHETIC_CREDENTIAL not in str(finding)


class TestNonSecretAssignmentsUnchanged:
    """Category D: Non-secret variables remain untouched and clean."""

    @pytest.mark.parametrize("non_secret_line", [
        '+ user_key = "customer_reference_value_12345"',
        '+ cache_key = "cache_prefix_item_12345"',
        '+ primary_key = "id_column_identifier_12345"',
    ])
    def test_non_secret_variables_are_not_flagged_or_redacted(self, non_secret_line):
        findings = scan_security_issues(non_secret_line, "models.py")
        assert len(findings) == 0


class TestFindingMetadataPreserved:
    """Category E: Finding location, severity, diff side, and metadata preservation."""

    def test_metadata_integrity_with_redaction(self):
        diff = (
            "diff --git a/services/auth.py b/services/auth.py\n"
            "--- a/services/auth.py\n"
            "+++ b/services/auth.py\n"
            "@@ -10,3 +10,4 @@\n"
            " import os\n"
            f'+ API_TOKEN = "{SYNTHETIC_CREDENTIAL}"\n'
            " return True\n"
        )
        agent = ReviewAgent()
        req = ReviewRequest(diff_content=diff, title="Test PR with Secret")
        res = agent.execute_review(req)

        secret_finding = next((f for f in res.findings if "Hardcoded Secret" in f.title), None)
        assert secret_finding is not None
        assert secret_finding.severity == SeverityLevel.CRITICAL
        assert secret_finding.location.file_path == "services/auth.py"
        assert secret_finding.location.start_line == 11
        assert secret_finding.location.line_side == LineSide.NEW
        assert secret_finding.location.code_context == 'API_TOKEN = "[REDACTED]"'
        assert SYNTHETIC_CREDENTIAL not in str(secret_finding.model_dump())


class TestAPISerializationRedaction:
    """Category F: Full API review route serialization check."""

    def test_api_review_endpoint_redacts_secret_in_response(self):
        client = TestClient(app)
        diff = (
            "diff --git a/services/auth.py b/services/auth.py\n"
            "--- a/services/auth.py\n"
            "+++ b/services/auth.py\n"
            "@@ -10,3 +10,4 @@\n"
            " import os\n"
            f'+ JWT_SECRET_KEY = "{SYNTHETIC_CREDENTIAL}"\n'
            " return True\n"
        )
        payload = {"diff_content": diff, "title": "PR with Synthetic Secret"}
        response = client.post("/api/review", json=payload)
        assert response.status_code == 200

        res_json = response.json()
        findings = res_json.get("findings", [])
        assert len(findings) >= 1

        # Check all string values in the entire findings list
        finding_strings = _recursively_find_strings(findings)
        for s in finding_strings:
            assert SYNTHETIC_CREDENTIAL not in s, f"Synthetic secret leaked in finding field: {s}"

        # Specifically assert that the code_context is redacted
        secret_f = next(f for f in findings if "Hardcoded Secret" in f.get("title", ""))
        assert secret_f["location"]["code_context"] == 'JWT_SECRET_KEY = "[REDACTED]"'


class TestSSESerializationRedaction:
    """Category G: Full SSE streaming review route serialization check."""

    def test_sse_review_stream_redacts_secret_in_all_events(self):
        client = TestClient(app)
        diff = (
            "diff --git a/services/auth.py b/services/auth.py\n"
            "--- a/services/auth.py\n"
            "+++ b/services/auth.py\n"
            "@@ -10,3 +10,4 @@\n"
            " import os\n"
            f'+ AWS_SECRET_KEY = "{SYNTHETIC_CREDENTIAL}"\n'
            " return True\n"
        )
        payload = {"diff_content": diff, "title": "SSE PR with Synthetic Secret"}
        response = client.post("/api/review/stream", json=payload)
        assert response.status_code == 200

        # Parse SSE stream
        sse_lines = response.text.splitlines()
        completed_data = None
        for line in sse_lines:
            if line.startswith("data:"):
                raw_data = line[5:].strip()
                try:
                    event_data = json.loads(raw_data)
                    # Check if this event contains the completed ReviewResponse
                    if "review_id" in event_data and "findings" in event_data:
                        completed_data = event_data
                except json.JSONDecodeError:
                    pass

        assert completed_data is not None, "Completed SSE event not found in stream"
        findings = completed_data.get("findings", [])
        assert len(findings) >= 1

        # Check all strings in completed payload
        all_finding_strings = _recursively_find_strings(findings)
        for s in all_finding_strings:
            assert SYNTHETIC_CREDENTIAL not in s, f"Synthetic secret leaked in SSE event: {s}"

        secret_f = next(f for f in findings if "Hardcoded Secret" in f.get("title", ""))
        assert secret_f["location"]["code_context"] == 'AWS_SECRET_KEY = "[REDACTED]"'


class TestRegressionIntegrity:
    """Category H: Non-secret findings and clean PR regression."""

    def test_sql_injection_evidence_is_not_redacted(self):
        sqli_line = '+ cursor.execute(f"SELECT * FROM users WHERE email = \'{user_email}\'")'
        findings = scan_security_issues(sqli_line, "auth.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SQLI-001"
        assert "[REDACTED]" not in findings[0]["matched_code"]
        assert "cursor.execute" in findings[0]["matched_code"]

    def test_clean_pr_remains_clean(self):
        agent = ReviewAgent()
        req = ReviewRequest(
            diff_content=SAMPLE_CLEAN_PR.diff_content,
            title=SAMPLE_CLEAN_PR.title
        )
        res = agent.execute_review(req)
        assert res.summary.verdict in ("APPROVED", "APPROVED_WITH_COMMENTS")
        assert len(res.findings) == 0

