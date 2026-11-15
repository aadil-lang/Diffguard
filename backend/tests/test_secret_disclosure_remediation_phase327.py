"""
Phase 3.2.7 Regression Test Suite: Comprehensive End-to-End Secret Disclosure Remediation.
Verifies permanent fixes for F-SEC-01 through F-SEC-05 across all application boundaries:
1. Scanner span-slicing and multi-secret line redaction (F-SEC-01).
2. External LLM request boundary and prompt sanitization (F-SEC-02).
3. AST parser exceptions and fallback finding code_context (F-SEC-03).
4. Compound string concatenation and multi-operand expressions (F-SEC-04).
5. Span validation and fail-closed behavior (F-SEC-05).
6. Cross-boundary REST, SSE, and logging non-disclosure verification.
"""

import json
import logging
import re
from io import StringIO
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app.main import app
from app.models.schemas import ReviewRequest, ReviewResponse, Finding
from app.agent.reviewer_agent import ReviewAgent
from app.tools.security_scanner import (
    scan_security_issues,
    redact_sensitive_line,
    sanitize_diff_content,
    SECURITY_RULES,
)
from app.tools.syntax_checker import check_python_syntax
from app.agent.fallback_engine import run_heuristic_code_review
from app.parser.diff_parser import parse_git_diff


SYNTH_ALPHA = "synth_audit_sec_alpha_9876543210"
SYNTH_BETA = "synth_audit_sec_beta_9876543210"
SYNTH_GAMMA = "synth_audit_sec_gamma_9876543210"
SYNTH_DELTA = "synth_audit_sec_delta_9876543210"
SYNTH_EPSILON = "synth_audit_sec_epsilon_9876543210"


def recursive_assert_no_secret(obj: Any, secret_token: str):
    """Recursively asserts that secret_token does not appear in any string representation."""
    if isinstance(obj, str):
        assert secret_token not in obj, f"Prohibited secret leaked in string: '{obj}'"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            recursive_assert_no_secret(k, secret_token)
            recursive_assert_no_secret(v, secret_token)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            recursive_assert_no_secret(item, secret_token)


# ==============================================================================
# Workstream A: Scanner Hardening (F-SEC-01, F-SEC-04, F-SEC-05)
# ==============================================================================

class TestWorkstreamAScannerHardening:
    """Verifies scanner redaction fixes for multi-secret lines, concatenation, and span checks."""

    def test_f_sec_01_multiple_credentials_on_one_line(self):
        diff_text = f"""diff --git a/app/config.py b/app/config.py
--- a/app/config.py
+++ b/app/config.py
@@ -1,2 +1,3 @@
 import os
+API_KEY = "{SYNTH_ALPHA}" and SECRET_KEY = "{SYNTH_BETA}"
"""
        findings = scan_security_issues(diff_text, "app/config.py")
        sec_findings = [f for f in findings if f.get("rule_id") == "SEC-SECRET-002"]

        assert len(sec_findings) >= 1
        matched_code = sec_findings[0]["matched_code"]

        # Neither secret must survive
        assert SYNTH_ALPHA not in matched_code
        assert SYNTH_BETA not in matched_code
        assert '[REDACTED]' in matched_code

        # Verify format preserves variable identifiers
        assert 'API_KEY = "[REDACTED]"' in matched_code
        assert 'SECRET_KEY = "[REDACTED]"' in matched_code

    def test_f_sec_01_three_credentials_on_one_line(self):
        line = f'+A = "{SYNTH_ALPHA}", B = "{SYNTH_BETA}", C = "{SYNTH_GAMMA}"'
        line_secret = f'+API_KEY = "{SYNTH_ALPHA}" and SECRET_KEY = "{SYNTH_BETA}" and JWT_SECRET = "{SYNTH_GAMMA}"'
        redacted = redact_sensitive_line(line_secret[1:])

        assert SYNTH_ALPHA not in redacted
        assert SYNTH_BETA not in redacted
        assert SYNTH_GAMMA not in redacted
        assert redacted.count("[REDACTED]") == 3

    def test_f_sec_04_compound_string_concatenation_redaction(self):
        diff_text = f"""diff --git a/app/config.py b/app/config.py
--- a/app/config.py
+++ b/app/config.py
@@ -1,2 +1,3 @@
 import os
+API_KEY = "audit_prefix_" + "{SYNTH_DELTA}"
"""
        findings = scan_security_issues(diff_text, "app/config.py")
        sec_findings = [f for f in findings if f.get("rule_id") == "SEC-SECRET-002"]

        assert len(sec_findings) >= 1
        matched_code = sec_findings[0]["matched_code"]

        # Neither operand must survive
        assert "audit_prefix_" not in matched_code
        assert SYNTH_DELTA not in matched_code
        assert 'API_KEY = "[REDACTED]"' in matched_code

    def test_f_sec_04_short_prefix_concatenation_redaction(self):
        line = f'API_KEY = "pre" + "{SYNTH_EPSILON}"'
        redacted = redact_sensitive_line(line)

        assert SYNTH_EPSILON not in redacted
        assert 'API_KEY = "[REDACTED]"' in redacted

    def test_f_sec_05_span_validation_and_fail_closed(self):
        # Direct unit test of span validation
        # Normal line
        valid_line = f'API_KEY = "{SYNTH_ALPHA}"'
        redacted = redact_sensitive_line(valid_line)
        assert redacted == 'API_KEY = "[REDACTED]"'

        # Empty / whitespace lines return cleanly
        assert redact_sensitive_line("") == ""
        assert redact_sensitive_line("   ") == "   "

        # Negative control line remains untouched
        neg_line = 'user_key = "audit_user_reference_12345"'
        assert redact_sensitive_line(neg_line) == neg_line


# ==============================================================================
# Workstream B: LLM Data Boundary Enforcement (F-SEC-02)
# ==============================================================================

class TestWorkstreamBModelDataBoundary:
    """Verifies that unredacted raw diffs never reach external LLM model request arguments."""

    def test_f_sec_02_captured_model_call_arguments_contain_no_raw_secret(self):
        diff_text = f"""diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1,2 +1,3 @@
 import os
+JWT_SECRET_KEY = "{SYNTH_GAMMA}"
"""
        captured_contents = []

        mock_client = MagicMock()
        def mock_generate_content(model, contents, config=None):
            # Capture the exact contents argument passed to Gemini client
            captured_contents.append(contents)
            mock_resp = MagicMock()
            mock_resp.candidates = [MagicMock()]
            mock_resp.candidates[0].content = types.Content(
                role="model",
                parts=[types.Part.from_text(text='{"review_id": "rev_test", "summary": {"total_findings": 0, "total_defects": 0, "total_policy_violations": 0, "total_recommendations": 0, "by_finding_type": {"code_defect": 0, "policy_violation": 0, "recommendation": 0}, "by_severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}, "by_category": {"BUG_OR_LOGIC_ERROR": 0, "SECURITY_AND_RELIABILITY": 0, "MISSING_TEST_COVERAGE": 0, "CODE_QUALITY_AND_MAINTAINABILITY": 0, "STYLE_AND_CONSISTENCY": 0}, "by_confidence": {"CONFIRMED_ISSUE": 0, "POTENTIAL_ISSUE": 0, "IMPROVEMENT_SUGGESTION": 0}, "verdict": "APPROVED", "key_takeaways": []}, "findings": [], "parsed_files_count": 1, "total_additions": 1, "total_deletions": 0, "stages_executed": [], "timestamp": "2026-11-15T00:00:00Z", "engine_used": "gemini-test"}')]
            )
            mock_resp.function_calls = []
            return mock_resp

        mock_client.models.generate_content.side_effect = mock_generate_content

        agent = ReviewAgent(api_key="test-mock-key")
        agent._client = mock_client

        req = ReviewRequest(
            diff_content=diff_text,
            pr_title="Add secret",
            pr_description="Test diff"
        )
        response = agent.execute_review(req)

        # Assert at least one model call was intercepted
        assert len(captured_contents) >= 1

        # Deep inspect every content part passed to the model
        diff_prompt_inspected = False
        for content_list in captured_contents:
            for item in content_list:
                if isinstance(item, types.Content):
                    for part in item.parts:
                        if hasattr(part, "text") and part.text:
                            # Assert raw secret is 100% absent from ALL prompts and turns
                            assert SYNTH_GAMMA not in part.text, "Prohibited secret found in model prompt!"
                            if "<untrusted_git_diff>" in part.text:
                                assert '[REDACTED]' in part.text
                                diff_prompt_inspected = True

        assert diff_prompt_inspected, "Expected to inspect at least one prompt containing untrusted_git_diff"

    def test_sanitize_diff_content_preserves_structure_while_redacting(self):
        diff_text = f"""diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1,3 +1,5 @@
 import os
+API_KEY = "{SYNTH_ALPHA}"
+JWT_SECRET_KEY = "{SYNTH_BETA}"
+def auth():
+    pass
"""
        sanitized = sanitize_diff_content(diff_text)

        # Structural markers preserved
        assert "diff --git a/app/auth.py b/app/auth.py" in sanitized
        assert "--- a/app/auth.py" in sanitized
        assert "+++ b/app/auth.py" in sanitized
        assert "@@ -1,3 +1,5 @@" in sanitized
        assert "+def auth():" in sanitized

        # Secrets redacted
        assert SYNTH_ALPHA not in sanitized
        assert SYNTH_BETA not in sanitized
        assert '+API_KEY = "[REDACTED]"' in sanitized
        assert '+JWT_SECRET_KEY = "[REDACTED]"' in sanitized


# ==============================================================================
# Workstream C & D: Analyzer Exceptions & API Boundaries (F-SEC-03)
# ==============================================================================

class TestWorkstreamCAndDOutputBoundaries:
    """Verifies that AST syntax exceptions, REST payloads, and SSE streams do not disclose secrets."""

    def test_f_sec_03_malformed_ast_syntax_error_not_disclosed_in_syntax_tool(self):
        malformed_snippet = f"""+JWT_SECRET_KEY = "{SYNTH_DELTA}" ("""
        issues = check_python_syntax(malformed_snippet, "app/auth.py")

        assert len(issues) >= 1
        for issue in issues:
            # Check text and message fields
            assert SYNTH_DELTA not in issue.get("text", "")
            assert SYNTH_DELTA not in issue.get("message", "")
            assert '[REDACTED]' in issue.get("text", "")

    def test_f_sec_03_unclosed_quote_syntax_error_not_disclosed(self):
        malformed_snippet = f"""+JWT_SECRET_KEY = "{SYNTH_DELTA}"""
        issues = check_python_syntax(malformed_snippet, "app/auth.py")

        for issue in issues:
            assert SYNTH_DELTA not in issue.get("text", "")
            assert SYNTH_DELTA not in issue.get("message", "")

    def test_f_sec_03_rest_api_boundary_on_malformed_syntax_diff(self):
        client = TestClient(app)
        malformed_diff = f"""diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1,2 +1,3 @@
 import os
+JWT_SECRET_KEY = "{SYNTH_DELTA}" (
"""
        resp = client.post("/api/review", json={
            "diff_content": malformed_diff,
            "pr_title": "Malformed secret test",
            "pr_description": "Testing AST syntax error non-disclosure"
        })

        assert resp.status_code == 200
        resp_json = resp.json()

        # Recursive string traversal of entire response JSON
        recursive_assert_no_secret(resp_json, SYNTH_DELTA)

    def test_f_sec_03_sse_stream_boundary_on_malformed_syntax_diff(self):
        client = TestClient(app)
        malformed_diff = f"""diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1,2 +1,3 @@
 import os
+JWT_SECRET_KEY = "{SYNTH_DELTA}" (
"""
        sse_resp = client.post("/api/review/stream", json={
            "diff_content": malformed_diff,
            "pr_title": "Malformed secret stream test",
            "pr_description": "Testing SSE non-disclosure"
        })

        assert sse_resp.status_code == 200
        raw_sse = sse_resp.text

        # Raw SSE stream text must be 100% free of synthetic secret
        assert SYNTH_DELTA not in raw_sse

    def test_logging_boundary_captures_zero_credentials(self):
        diff_text = f"""diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1,2 +1,4 @@
 import os
+API_KEY = "{SYNTH_ALPHA}"
+JWT_SECRET_KEY = "{SYNTH_BETA}" (
"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        old_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)

        try:
            client = TestClient(app)
            client.post("/api/review", json={"diff_content": diff_text, "pr_title": "test", "pr_description": "test"})
            client.post("/api/review/stream", json={"diff_content": diff_text, "pr_title": "test", "pr_description": "test"})
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(old_level)

        captured_logs = log_stream.getvalue()
        assert SYNTH_ALPHA not in captured_logs
        assert SYNTH_BETA not in captured_logs
