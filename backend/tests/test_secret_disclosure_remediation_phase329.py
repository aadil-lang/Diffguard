"""
Phase 3.2.9 Regression Test Suite: Deleted-Line & Containerized Secret Disclosure Remediation.
Verifies permanent fixes for:
- F-SEC-06: Deleted diff lines sanitization across prompt, tool dispatcher, hunk inspector, and model calls.
- F-SEC-07: Containerized secret assignments (lists, tuples, dicts, unclosed, compound, and multi-value).
- Preservation of F-SEC-01 through F-SEC-05.
- Recursive non-disclosure verification across REST, SSE, and tool boundaries.
"""

import json
import re
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app.main import app
from app.models.schemas import ReviewRequest, ReviewResponse, Finding
from app.models.diff_models import ParsedDiff
from app.agent.reviewer_agent import ReviewAgent
from app.tools.security_scanner import (
    scan_security_issues,
    redact_sensitive_line,
    sanitize_diff_content,
    SECURITY_RULES,
    UNCLOSED_SECRET_PATTERN,
)
from app.tools.syntax_checker import check_python_syntax
from app.agent.fallback_engine import run_heuristic_code_review
from app.parser.diff_parser import parse_git_diff
from app.tools.tool_dispatcher import ToolDispatcher
from app.tools.hunk_inspector import execute_inspect_diff_hunk, execute_inspect_patch_context
from app.tools.tool_schemas import InspectDiffHunkArgs, InspectPatchContextArgs


SYNTH_DEL_1 = "synth_del_sec_one_123456789012"
SYNTH_DEL_2 = "synth_del_sec_two_123456789012"
SYNTH_CONT_LIST = "synth_cont_list_sec_1234567890"
SYNTH_CONT_DICT = "synth_cont_dict_sec_1234567890"
SYNTH_CONT_TUPLE = "synth_cont_tup_sec_1234567890"
SYNTH_CONT_MULTI_1 = "synth_multi_one_sec_123456789"
SYNTH_CONT_MULTI_2 = "synth_multi_two_sec_123456789"
SYNTH_CONT_NESTED = "synth_nested_sec_123456789012"
SYNTH_CONT_CONCAT = "synth_concat_sec_123456789012"
SYNTH_CONT_UNCLOSED = "synth_unclosed_sec_123456789"


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
# Workstream 1: F-SEC-06 Deleted Diff Line Remediation
# ==============================================================================

class TestFSec06DeletedLineDisclosure:
    """Verifies that deleted diff lines are sanitized across all application paths."""

    def test_single_deleted_source_line_is_sanitized(self):
        diff_text = f"""diff --git a/services/auth.py b/services/auth.py
index 1234567..89abcdef 100644
--- a/services/auth.py
+++ b/services/auth.py
@@ -10,3 +10,3 @@
 import os
-API_KEY = "{SYNTH_DEL_1}"
+API_KEY = os.getenv("API_KEY")
"""
        sanitized = sanitize_diff_content(diff_text)

        assert SYNTH_DEL_1 not in sanitized
        assert '-API_KEY = "[REDACTED]"' in sanitized
        assert "+API_KEY = os.getenv(\"API_KEY\")" in sanitized
        assert "diff --git a/services/auth.py b/services/auth.py" in sanitized
        assert "--- a/services/auth.py" in sanitized
        assert "+++ b/services/auth.py" in sanitized
        assert "@@ -10,3 +10,3 @@" in sanitized

    def test_multiple_deleted_secrets_on_same_line_and_across_lines(self):
        diff_text = f"""diff --git a/services/config.py b/services/config.py
--- a/services/config.py
+++ b/services/config.py
@@ -1,4 +1,2 @@
-API_KEY = "{SYNTH_DEL_1}" and SECRET_KEY = "{SYNTH_DEL_2}"
-JWT_SECRET = "{SYNTH_DEL_1}"
+API_KEY = os.getenv("API_KEY")
"""
        sanitized = sanitize_diff_content(diff_text)

        assert SYNTH_DEL_1 not in sanitized
        assert SYNTH_DEL_2 not in sanitized
        assert '-API_KEY = "[REDACTED]" and SECRET_KEY = "[REDACTED]"' in sanitized
        assert '-JWT_SECRET = "[REDACTED]"' in sanitized

    def test_diff_structure_and_headers_strictly_preserved(self):
        diff_text = f"""diff --git a/app.py b/app.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/app.py
@@ -0,0 +1,5 @@
+import os
+-old_secret_key = "{SYNTH_DEL_1}"
+new_var = "clean"
"""
        sanitized = sanitize_diff_content(diff_text)
        assert "--- /dev/null" in sanitized
        assert "+++ b/app.py" in sanitized
        assert "new file mode 100644" in sanitized
        assert '-old_secret_key = "[REDACTED]"' in sanitized
        assert SYNTH_DEL_1 not in sanitized

    def test_tool_boundary_inspect_diff_hunk_returns_redacted_deleted_lines(self):
        diff_text = f"""diff --git a/services/auth.py b/services/auth.py
index 1234567..89abcdef 100644
--- a/services/auth.py
+++ b/services/auth.py
@@ -10,3 +10,3 @@
 import os
-API_KEY = "{SYNTH_DEL_1}"
+API_KEY = os.getenv("API_KEY")
"""
        sanitized_diff = sanitize_diff_content(diff_text)
        parsed = parse_git_diff(sanitized_diff)
        args = InspectDiffHunkArgs(file_path="services/auth.py", hunk_index=0)
        hunk_result = execute_inspect_diff_hunk(parsed, args)

        assert SYNTH_DEL_1 not in str(hunk_result)
        assert hunk_result["deleted_lines"] == ['API_KEY = "[REDACTED]"']
        assert '-API_KEY = "[REDACTED]"' in hunk_result["raw_hunk"]

    def test_tool_boundary_inspect_patch_context_returns_redacted_deleted_lines(self):
        diff_text = f"""diff --git a/services/auth.py b/services/auth.py
index 1234567..89abcdef 100644
--- a/services/auth.py
+++ b/services/auth.py
@@ -10,3 +10,3 @@
 import os
-API_KEY = "{SYNTH_DEL_1}"
+API_KEY = os.getenv("API_KEY")
"""
        sanitized_diff = sanitize_diff_content(diff_text)
        parsed = parse_git_diff(sanitized_diff)
        args = InspectPatchContextArgs(file_path="services/auth.py", start_line=11, line_side="old")
        ctx_result = execute_inspect_patch_context(parsed, args)

        assert SYNTH_DEL_1 not in str(ctx_result)
        assert ctx_result["lines"][0]["content"] == 'API_KEY = "[REDACTED]"'

    def test_model_boundary_arguments_contain_no_deleted_secret(self):
        diff_text = f"""diff --git a/services/auth.py b/services/auth.py
--- a/services/auth.py
+++ b/services/auth.py
@@ -10,3 +10,3 @@
 import os
-API_KEY = "{SYNTH_DEL_1}"
+API_KEY = os.getenv("API_KEY")
"""
        captured_contents = []

        mock_client = MagicMock()
        def mock_generate_content(model, contents, config=None):
            captured_contents.append(contents)
            mock_resp = MagicMock()
            mock_resp.candidates = [
                MagicMock(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=json.dumps({
                            "findings": [],
                            "summary": {
                                "verdict": "APPROVED",
                                "risk_score": 0,
                                "assessment": "Clean rotation.",
                                "key_risks": [],
                                "positive_notes": []
                            }
                        }))]
                    )
                )
            ]
            mock_resp.function_calls = []
            return mock_resp

        mock_client.models.generate_content.side_effect = mock_generate_content

        with patch("app.agent.reviewer_agent.genai.Client", return_value=mock_client):
            agent = ReviewAgent(api_key="mock_key")
            req = ReviewRequest(diff_content=diff_text, title="Secret Rotation PR")
            agent.execute_review(req)

        assert len(captured_contents) >= 1
        for turn_contents in captured_contents:
            for item in turn_contents:
                for part in item.parts:
                    if part.text:
                        assert SYNTH_DEL_1 not in part.text


# ==============================================================================
# Workstream 2: F-SEC-07 Containerized Secret Assignment Remediation
# ==============================================================================

class TestFSec07ContainerizedSecretDisclosure:
    """Verifies recognition and non-disclosure for containerized secret assignments."""

    def test_01_unclosed_secret_in_list(self):
        line = f'API_KEY = ["{SYNTH_CONT_UNCLOSED}'
        redacted = redact_sensitive_line(line)
        assert SYNTH_CONT_UNCLOSED not in redacted
        assert redacted == 'API_KEY = ["[REDACTED]"'

    def test_02_unclosed_secret_in_dict(self):
        line = f'API_KEY = {{"value": "{SYNTH_CONT_DICT}'
        redacted = redact_sensitive_line(line)
        assert SYNTH_CONT_DICT not in redacted
        assert redacted == 'API_KEY = {"value": "[REDACTED]"'

    def test_03_unclosed_secret_in_tuple(self):
        line = f'API_KEY = ("{SYNTH_CONT_TUPLE}'
        redacted = redact_sensitive_line(line)
        assert SYNTH_CONT_TUPLE not in redacted
        assert redacted == 'API_KEY = ("[REDACTED]"'

    def test_04_valid_containerized_secret_assignments(self):
        # List
        l_line = f'API_KEY = ["{SYNTH_CONT_LIST}"]'
        assert redact_sensitive_line(l_line) == 'API_KEY = ["[REDACTED]"]'

        # Dict
        d_line = f'API_KEY = {{"value": "{SYNTH_CONT_DICT}"}}'
        assert redact_sensitive_line(d_line) == 'API_KEY = {"value": "[REDACTED]"}'

        # Tuple
        t_line = f'API_KEY = ("{SYNTH_CONT_TUPLE}",)'
        assert redact_sensitive_line(t_line) == 'API_KEY = ("[REDACTED]",)'

    def test_05_multiple_secret_values_in_container(self):
        # List with plural variable name
        multi_list = f'API_KEYS = ["{SYNTH_CONT_MULTI_1}", "{SYNTH_CONT_MULTI_2}"]'
        redacted = redact_sensitive_line(multi_list)
        assert SYNTH_CONT_MULTI_1 not in redacted
        assert SYNTH_CONT_MULTI_2 not in redacted
        assert redacted == 'API_KEYS = ["[REDACTED]", "[REDACTED]"]'

        # Dict with multiple sensitive keys
        multi_dict = f'CONFIG = {{"api_key": "{SYNTH_CONT_MULTI_1}", "secret_token": "{SYNTH_CONT_MULTI_2}"}}'
        redacted_d = redact_sensitive_line(multi_dict)
        assert SYNTH_CONT_MULTI_1 not in redacted_d
        assert SYNTH_CONT_MULTI_2 not in redacted_d
        assert redacted_d == 'CONFIG = {"api_key": "[REDACTED]", "secret_token": "[REDACTED]"}'

    def test_06_nested_containers(self):
        line = f'API_KEY = [["{SYNTH_CONT_NESTED}"]]'
        redacted = redact_sensitive_line(line)
        assert SYNTH_CONT_NESTED not in redacted
        assert redacted == 'API_KEY = [["[REDACTED]"]]'

    def test_07_mixed_single_and_double_quotes(self):
        line_sq = f"API_KEY = ['{SYNTH_CONT_LIST}']"
        assert redact_sensitive_line(line_sq) == "API_KEY = ['[REDACTED]']"

        mixed = f'API_KEYS = ["{SYNTH_CONT_MULTI_1}", \'{SYNTH_CONT_MULTI_2}\']'
        redacted_mixed = redact_sensitive_line(mixed)
        assert SYNTH_CONT_MULTI_1 not in redacted_mixed
        assert SYNTH_CONT_MULTI_2 not in redacted_mixed
        assert redacted_mixed == 'API_KEYS = ["[REDACTED]", \'[REDACTED]\']'

    def test_08_containerized_compound_concatenation(self):
        line = f'API_KEY = ["prefix_" + "{SYNTH_CONT_CONCAT}" + "_suffix"]'
        redacted = redact_sensitive_line(line)
        assert SYNTH_CONT_CONCAT not in redacted
        assert redacted == 'API_KEY = ["[REDACTED]"]'

    def test_09_malformed_container_syntax(self):
        # Unclosed quote before closing bracket
        line_bracket = f'API_KEY = ["{SYNTH_CONT_UNCLOSED}]'
        redacted = redact_sensitive_line(line_bracket)
        assert SYNTH_CONT_UNCLOSED not in redacted
        assert '[REDACTED]' in redacted

        # Unclosed quote with trailing comment
        line_comment = f'API_KEY = ["{SYNTH_CONT_UNCLOSED} # inline comment'
        redacted_comment = redact_sensitive_line(line_comment)
        assert SYNTH_CONT_UNCLOSED not in redacted_comment
        assert '[REDACTED]' in redacted_comment

    def test_10_ordinary_non_secret_containers_remain_untouched(self):
        non_secrets = [
            'USERS = ["alice", "bob"]',
            'DATA = {"name": "diffguard"}',
            'ITEMS = ("apple", "banana")',
            'user_key = "customer_reference_value_12345"',
            'SORT_KEYS = ["name", "date"]',
            'ports = [8000, 8080]',
        ]
        for ns in non_secrets:
            assert redact_sensitive_line(ns) == ns, f"False positive triggered on: '{ns}'"

    def test_syntax_exception_protection_on_containerized_syntax_error(self):
        malformed_snippet = f'+API_KEY = ["{SYNTH_CONT_UNCLOSED}'
        issues = check_python_syntax(malformed_snippet, "app/config.py")

        assert len(issues) >= 1
        for issue in issues:
            assert SYNTH_CONT_UNCLOSED not in issue.get("text", "")
            assert SYNTH_CONT_UNCLOSED not in issue.get("message", "")
            assert '[REDACTED]' in issue.get("text", "")


# ==============================================================================
# Workstream 3: Preservation of F-SEC-01 Through F-SEC-05
# ==============================================================================

class TestPreservationOfPreviousHardening:
    """Verifies no regression of F-SEC-01 through F-SEC-05."""

    def test_f_sec_01_preserved_multi_secret_line_reverse_slice(self):
        line = f'API_KEY = "{SYNTH_DEL_1}" and SECRET_KEY = "{SYNTH_DEL_2}"'
        redacted = redact_sensitive_line(line)
        assert SYNTH_DEL_1 not in redacted
        assert SYNTH_DEL_2 not in redacted
        assert redacted == 'API_KEY = "[REDACTED]" and SECRET_KEY = "[REDACTED]"'

    def test_f_sec_02_preserved_diff_sanitizer_added_and_context(self):
        diff = f"""diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
  API_KEY = "{SYNTH_DEL_1}"
+SECRET_KEY = "{SYNTH_DEL_2}"
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_DEL_1 not in sanitized
        assert SYNTH_DEL_2 not in sanitized
        assert ' API_KEY = "[REDACTED]"' in sanitized
        assert '+SECRET_KEY = "[REDACTED]"' in sanitized

    def test_f_sec_03_preserved_syntax_error_sanitization(self):
        malformed = f'+JWT_SECRET_KEY = "{SYNTH_DEL_1}" ('
        issues = check_python_syntax(malformed, "auth.py")
        assert len(issues) >= 1
        for issue in issues:
            assert SYNTH_DEL_1 not in issue.get("text", "")
            assert SYNTH_DEL_1 not in issue.get("message", "")

    def test_f_sec_04_preserved_compound_concatenation(self):
        line = f'API_KEY = "prefix_" + "{SYNTH_DEL_1}" + "_suffix"'
        redacted = redact_sensitive_line(line)
        assert SYNTH_DEL_1 not in redacted
        assert redacted == 'API_KEY = "[REDACTED]"'

    def test_f_sec_05_preserved_strict_bounds_and_fail_closed(self):
        valid_line = f'API_KEY = "{SYNTH_DEL_1}"'
        assert redact_sensitive_line(valid_line) == 'API_KEY = "[REDACTED]"'
        assert redact_sensitive_line("") == ""
        assert redact_sensitive_line("   ") == "   "
        neg_line = 'user_key = "customer_reference_value_12345"'
        assert redact_sensitive_line(neg_line) == neg_line


# ==============================================================================
# Workstream 4: Full Pipeline REST and SSE Verification
# ==============================================================================

class TestFullPipelineDisclosureSafe:
    """Verifies that complete serialized REST and SSE payloads contain zero raw credentials."""

    def test_rest_api_review_pipeline_with_deleted_and_container_secrets(self):
        client = TestClient(app)
        patch_text = f"""diff --git a/services/auth.py b/services/auth.py
--- a/services/auth.py
+++ b/services/auth.py
@@ -1,4 +1,4 @@
 import os
-API_KEY = "{SYNTH_DEL_1}"
+API_KEY = ["{SYNTH_CONT_LIST}"]
+USERS = ["alice", "bob"]
"""
        res = client.post("/api/review", json={"diff_content": patch_text, "title": "Audit Review"})
        assert res.status_code == 200
        data = res.json()

        # Recursive audit across entire JSON payload
        recursive_assert_no_secret(data, SYNTH_DEL_1)
        recursive_assert_no_secret(data, SYNTH_CONT_LIST)

    def test_sse_stream_review_pipeline_with_deleted_and_container_secrets(self):
        client = TestClient(app)
        patch_text = f"""diff --git a/services/auth.py b/services/auth.py
--- a/services/auth.py
+++ b/services/auth.py
@@ -1,4 +1,4 @@
 import os
-API_KEY = "{SYNTH_DEL_1}"
+API_KEY = ["{SYNTH_CONT_UNCLOSED}
"""
        with client.stream("POST", "/api/review/stream", json={"diff_content": patch_text, "title": "Audit Stream"}) as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if line.startswith("data:"):
                    raw_data = line[len("data:"):].strip()
                    if raw_data:
                        event_payload = json.loads(raw_data)
                        recursive_assert_no_secret(event_payload, SYNTH_DEL_1)
                        recursive_assert_no_secret(event_payload, SYNTH_CONT_UNCLOSED)
