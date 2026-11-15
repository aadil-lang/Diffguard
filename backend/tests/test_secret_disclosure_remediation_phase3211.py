"""
Phase 3.2.11 Regression Test Suite: Stateful Diff Redaction & Multiline Secret Disclosure Remediation.

Verifies permanent fixes for:
- F-SEC-08: Deleted diff lines beginning with hyphens, decrement operators, SQL/Lua comments, and YAML bullets.
- F-SEC-09: Diff-side-aware multi-line containerized secret assignments across added, deleted, and context lines.
- Short credential redaction across sensitive variable assignments (<12 chars) without static rule noise.
- Multi-line SyntaxError AST exception masking without credential leaks in text or context.
- Structural diff awareness preserving unified diff file headers (--- a/..., +++ b/...).
- Non-secret negative controls preserving legitimate code review functionality.
- Preservation of F-SEC-01 through F-SEC-07 across REST, SSE, and Tool boundaries.
"""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser.diff_parser import parse_git_diff
from app.tools.security_scanner import (
    scan_security_issues,
    redact_sensitive_line,
    sanitize_diff_content,
    sanitize_code_snippet,
    ContainerScopeTracker,
    SECURITY_RULES,
)
from app.tools.syntax_checker import check_python_syntax
from app.tools.hunk_inspector import execute_inspect_diff_hunk, execute_inspect_patch_context
from app.tools.tool_schemas import InspectDiffHunkArgs, InspectPatchContextArgs


# Synthetic test credentials (non-production, strictly synthetic)
SYNTH_HYPHEN_SQL = "synth_hyphen_sql_secret_1234567890"
SYNTH_HYPHEN_DECR = "synth_hyphen_decr_secret_123456789"
SYNTH_YAML_BULLET = "synth_yaml_bullet_secret_12345678"
SYNTH_THREE_DASH = "synth_three_dash_secret_123456789"

SYNTH_ML_LIST_1 = "synth_ml_list_val1_1234567890"
SYNTH_ML_LIST_2 = "synth_ml_list_val2_1234567890"
SYNTH_ML_DICT_VAL = "synth_ml_dict_val_1234567890"
SYNTH_ML_DEL_VAL = "synth_ml_del_val_1234567890"
SYNTH_ML_CTX_VAL = "synth_ml_ctx_val_1234567890"
SYNTH_ML_SYNTAX_ERR = "synth_ml_syntax_err_secret_12345"

SYNTH_SHORT_1 = "a"
SYNTH_SHORT_8 = "shortsec"
SYNTH_SHORT_11 = "sec11chars!"


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
# Workstream 1: F-SEC-08 Hyphenated & Deleted Diff Line Remediation
# ==============================================================================

class TestFSec08HyphenatedDeletedDiffLines:
    """Verifies that deleted lines starting with hyphens or comments are reliably sanitized."""

    def test_sql_lua_comment_deleted_line(self):
        diff = f"""diff --git a/queries.sql b/queries.sql
--- a/queries.sql
+++ b/queries.sql
@@ -10,3 +10,2 @@
---API_KEY = "{SYNTH_HYPHEN_SQL}"
-SELECT 1;
+SELECT 2;
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_HYPHEN_SQL not in sanitized
        assert '---API_KEY = "[REDACTED]"' in sanitized
        # File header must be preserved
        assert "--- a/queries.sql" in sanitized
        assert "+++ b/queries.sql" in sanitized

    def test_decrement_operator_deleted_line(self):
        diff = f"""diff --git a/app.js b/app.js
--- a/app.js
+++ b/app.js
@@ -5,3 +5,2 @@
---API_KEY = "{SYNTH_HYPHEN_DECR}";
-count--;
+count++;
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_HYPHEN_DECR not in sanitized
        assert '---API_KEY = "[REDACTED]";' in sanitized

    def test_yaml_bullet_deleted_line(self):
        diff = f"""diff --git a/config.yaml b/config.yaml
--- a/config.yaml
+++ b/config.yaml
@@ -1,4 +1,3 @@
 - name: service
--- API_KEY: "{SYNTH_YAML_BULLET}"
+-- API_KEY: "[REPLACE_ME]"
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_YAML_BULLET not in sanitized
        assert '--- API_KEY: "[REDACTED]"' in sanitized

    def test_three_hyphen_standalone_deleted_line(self):
        diff = f"""diff --git a/script.py b/script.py
--- a/script.py
+++ b/script.py
@@ -1,3 +1,2 @@
----API_KEY = "{SYNTH_THREE_DASH}"
-print("old")
+print("new")
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_THREE_DASH not in sanitized
        assert '----API_KEY = "[REDACTED]"' in sanitized

    def test_multi_file_and_multi_hunk_header_preservation(self):
        diff = f"""diff --git a/first.py b/first.py
--- a/first.py
+++ b/first.py
@@ -1,4 +1,3 @@
-API_KEY = "old_secret_first_123456789"
+API_KEY = "new_secret_first_123456789"
@@ -10,3 +9,2 @@
---API_KEY = "hunk2_secret_first_12345678"
+print("ok")
diff --git a/second.py b/second.py
--- a/second.py
+++ b/second.py
@@ -1,3 +1,2 @@
---API_KEY = "old_secret_second_12345678"
+print("second")
"""
        sanitized = sanitize_diff_content(diff)
        assert "old_secret_first_123456789" not in sanitized
        assert "new_secret_first_123456789" not in sanitized
        assert "hunk2_secret_first_12345678" not in sanitized
        assert "old_secret_second_12345678" not in sanitized
        # Verify file headers across both files are untouched
        assert "--- a/first.py" in sanitized
        assert "+++ b/first.py" in sanitized
        assert "--- a/second.py" in sanitized
        assert "+++ b/second.py" in sanitized


# ==============================================================================
# Workstream 2: F-SEC-09 Multi-Line Container Scope Tracking
# ==============================================================================

class TestFSec09MultilineContainerScopeTracking:
    """Verifies diff-side-aware multi-line container scope tracking."""

    def test_multiline_list_in_added_lines(self):
        diff = f"""diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1,2 +1,6 @@
+API_KEYS = [
+    "{SYNTH_ML_LIST_1}",
+    "{SYNTH_ML_LIST_2}",
+]
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_ML_LIST_1 not in sanitized
        assert SYNTH_ML_LIST_2 not in sanitized
        assert 'API_KEYS = [' in sanitized
        assert '+    "[REDACTED]",' in sanitized

    def test_multiline_dict_added_lines_preserves_keys(self):
        diff = f"""diff --git a/settings.py b/settings.py
--- a/settings.py
+++ b/settings.py
@@ -1,2 +1,6 @@
+AUTH_CONFIG = {{
+    "api_token": "{SYNTH_ML_DICT_VAL}",
+    "timeout": 30,
+}}
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_ML_DICT_VAL not in sanitized
        assert '"api_token": "[REDACTED]"' in sanitized
        assert '"timeout": 30' in sanitized

    def test_multiline_list_in_deleted_lines(self):
        diff = f"""diff --git a/keys.py b/keys.py
--- a/keys.py
+++ b/keys.py
@@ -1,5 +1,1 @@
-SECRET_TOKENS = [
-    "{SYNTH_ML_DEL_VAL}",
-]
+SECRET_TOKENS = []
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_ML_DEL_VAL not in sanitized
        assert '-    "[REDACTED]",' in sanitized

    def test_context_line_opens_container_scope_for_added_line(self):
        diff = f"""diff --git a/keys.py b/keys.py
--- a/keys.py
+++ b/keys.py
@@ -1,4 +1,5 @@
  PRIVATE_KEYS = [
+    "{SYNTH_ML_CTX_VAL}",
  ]
"""
        sanitized = sanitize_diff_content(diff)
        assert SYNTH_ML_CTX_VAL not in sanitized
        assert '+    "[REDACTED]",' in sanitized

    def test_interleaved_additions_and_deletions_maintain_independent_scopes(self):
        diff = f"""diff --git a/keys.py b/keys.py
--- a/keys.py
+++ b/keys.py
@@ -1,5 +1,5 @@
  API_KEYS = [
-    "old_multi_del_secret_1234567890",
+    "new_multi_add_secret_1234567890",
  ]
"""
        sanitized = sanitize_diff_content(diff)
        assert "old_multi_del_secret_1234567890" not in sanitized
        assert "new_multi_add_secret_1234567890" not in sanitized
        assert '-    "[REDACTED]",' in sanitized
        assert '+    "[REDACTED]",' in sanitized

    def test_scope_closes_on_closing_delimiter(self):
        diff = f"""diff --git a/keys.py b/keys.py
--- a/keys.py
+++ b/keys.py
@@ -1,6 +1,6 @@
+API_KEYS = [
+    "secret_inside_123456789012",
+]
+OTHER_LIST = [
+    "safe_element_outside_12345",
+]
"""
        sanitized = sanitize_diff_content(diff)
        assert "secret_inside_123456789012" not in sanitized
        assert "safe_element_outside_12345" in sanitized


# ==============================================================================
# Workstream 3: Multi-Line AST Syntax Error Context Protection
# ==============================================================================

class TestMultilineSyntaxErrorProtection:
    """Verifies that multi-line unclosed syntax errors do not leak secrets via SyntaxError."""

    def test_multiline_unclosed_container_syntax_error(self):
        bad_code = f"""API_KEY = [
    "{SYNTH_ML_SYNTAX_ERR}"
"""
        issues = check_python_syntax(bad_code, "bad_list.py")
        assert len(issues) >= 1
        for issue in issues:
            recursive_assert_no_secret(issue, SYNTH_ML_SYNTAX_ERR)

    def test_multiline_unclosed_dict_syntax_error(self):
        bad_code = f"""AUTH_MAP = {{
    "token": "{SYNTH_ML_SYNTAX_ERR}"
"""
        issues = check_python_syntax(bad_code, "bad_dict.py")
        assert len(issues) >= 1
        for issue in issues:
            recursive_assert_no_secret(issue, SYNTH_ML_SYNTAX_ERR)

    def test_sanitize_code_snippet_helper_directly(self):
        snippet = f"""API_KEY = [
    "{SYNTH_ML_SYNTAX_ERR}",
]"""
        sanitized = sanitize_code_snippet(snippet)
        assert SYNTH_ML_SYNTAX_ERR not in sanitized
        assert '"[REDACTED]"' in sanitized


# ==============================================================================
# Workstream 4: Short Credential Redaction (<12 chars)
# ==============================================================================

class TestShortCredentialRedaction:
    """Verifies that credentials shorter than 12 chars are redacted when assigned to sensitive variables."""

    @pytest.mark.parametrize("short_val", [SYNTH_SHORT_1, SYNTH_SHORT_8, SYNTH_SHORT_11, ""])
    def test_short_credential_redacted_in_standalone_assignment(self, short_val):
        line = f'API_KEY = "{short_val}"'
        redacted = redact_sensitive_line(line)
        assert redacted == 'API_KEY = "[REDACTED]"'

    def test_short_credential_redacted_in_container(self):
        diff = f"""diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
+API_KEYS = [
+    "{SYNTH_SHORT_1}",
+    "{SYNTH_SHORT_8}",
+]
"""
        sanitized = sanitize_diff_content(diff)
        assert f'"{SYNTH_SHORT_1}"' not in sanitized
        assert f'"{SYNTH_SHORT_8}"' not in sanitized
        assert '+    "[REDACTED]",' in sanitized

    def test_static_rule_sec_secret_002_retains_min_length_for_finding_generation(self):
        """Rule SEC-SECRET-002 should NOT trigger noisy findings for 1-character assignments."""
        single_char_diff = '+API_KEY = "x"\n'
        findings = scan_security_issues(single_char_diff, "test.py")
        secret_findings = [f for f in findings if f.get("rule_id") == "SEC-SECRET-002"]
        # Static detection avoids noise on 1 char
        assert len(secret_findings) == 0

        # But long credential (>= 12) DOES trigger finding
        long_diff = '+API_KEY = "long_secret_value_12345678"\n'
        findings_long = scan_security_issues(long_diff, "test.py")
        secret_findings_long = [f for f in findings_long if f.get("rule_id") == "SEC-SECRET-002"]
        assert len(secret_findings_long) == 1
        # And its matched_code is redacted!
        assert "long_secret_value_12345678" not in secret_findings_long[0].get("matched_code", "")
        assert "[REDACTED]" in secret_findings_long[0].get("matched_code", "")


# ==============================================================================
# Workstream 5: Non-Secret Negative Controls & Preserved Functionality
# ==============================================================================

class TestNonSecretNegativeControls:
    """Verifies that non-secret lines and containers are NOT improperly redacted."""

    def test_legitimate_variable_assignments_untouched(self):
        diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,4 +1,4 @@
-USER_NAME = "alice_wonderland"
+USER_NAME = "bob_builder"
-RETRIES = 5
+RETRIES = 10
"""
        sanitized = sanitize_diff_content(diff)
        assert "alice_wonderland" in sanitized
        assert "bob_builder" in sanitized
        assert "RETRIES = 10" in sanitized

    def test_legitimate_container_assignments_untouched(self):
        diff = """diff --git a/fruits.py b/fruits.py
--- a/fruits.py
+++ b/fruits.py
@@ -1,2 +1,5 @@
+FRUITS = [
+    "apple",
+    "banana",
+]
"""
        sanitized = sanitize_diff_content(diff)
        assert '"apple"' in sanitized
        assert '"banana"' in sanitized
        assert "[REDACTED]" not in sanitized


# ==============================================================================
# Workstream 6: End-to-End Pipeline & Tool Boundary Verification
# ==============================================================================

class TestEndToEndPipelineIntegrity:
    """Verifies that neither F-SEC-08 nor F-SEC-09 secrets leak through tools, REST, or SSE endpoints."""

    def test_hunk_inspector_sanitizes_hyphen_and_multiline_secrets(self):
        diff = f"""diff --git a/secret.py b/secret.py
--- a/secret.py
+++ b/secret.py
@@ -1,5 +1,5 @@
---API_KEY = "{SYNTH_HYPHEN_SQL}"
+API_KEYS = [
+    "{SYNTH_ML_LIST_1}",
+]
"""
        sanitized = sanitize_diff_content(diff)
        parsed = parse_git_diff(sanitized)
        hunk_args = InspectDiffHunkArgs(file_path="secret.py", hunk_index=0)
        hunk_res = execute_inspect_diff_hunk(parsed, hunk_args)

        recursive_assert_no_secret(hunk_res, SYNTH_HYPHEN_SQL)
        recursive_assert_no_secret(hunk_res, SYNTH_ML_LIST_1)

        ctx_args = InspectPatchContextArgs(file_path="secret.py", start_line=1, line_side="new")
        ctx_res = execute_inspect_patch_context(parsed, ctx_args)

        recursive_assert_no_secret(ctx_res, SYNTH_HYPHEN_SQL)
        recursive_assert_no_secret(ctx_res, SYNTH_ML_LIST_1)

    def test_rest_api_review_no_disclosure(self):
        client = TestClient(app)
        raw_diff = f"""diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1,5 +1,5 @@
---DELETED_KEY = "{SYNTH_HYPHEN_SQL}"
+API_KEYS = [
+    "{SYNTH_ML_LIST_1}",
+]
"""
        resp = client.post("/api/review", json={"diff_content": raw_diff, "title": "Phase 3.2.11 REST Test"})
        assert resp.status_code == 200
        data = resp.json()
        recursive_assert_no_secret(data, SYNTH_HYPHEN_SQL)
        recursive_assert_no_secret(data, SYNTH_ML_LIST_1)

    def test_sse_stream_review_no_disclosure(self):
        client = TestClient(app)
        raw_diff = f"""diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1,5 +1,5 @@
---DELETED_KEY = "{SYNTH_HYPHEN_SQL}"
+API_KEYS = [
+    "{SYNTH_ML_LIST_1}",
+]
"""
        with client.stream("POST", "/api/review/stream", json={"diff_content": raw_diff, "title": "Phase 3.2.11 Stream Test"}) as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if line.startswith("data:"):
                    raw_payload = line[len("data:"):].strip()
                    if raw_payload:
                        event_payload = json.loads(raw_payload)
                        recursive_assert_no_secret(event_payload, SYNTH_HYPHEN_SQL)
                        recursive_assert_no_secret(event_payload, SYNTH_ML_LIST_1)
