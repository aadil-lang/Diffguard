"""
Unit and regression tests for Phase 3.2.13:
1. SQL f-string false positive regression resolution.
2. F-SEC-10: JavaScript / TypeScript ES6 backtick-delimited credential detection & redaction.
3. Verification across single-line, containerized, multiline, and diff-line contexts.
"""

import pytest
from app.tools.security_scanner import (
    is_index_inside_quote,
    is_quote_count_odd,
    redact_sensitive_line,
    sanitize_diff_content,
    scan_security_issues,
)


class TestSQLFStringFalsePositive:
    def test_sql_fstring_password_not_detected_as_secret(self):
        sql_line = """        raw_query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password_hash}'" """
        # Line has balanced quotes
        odd, _ = is_quote_count_odd(sql_line)
        assert not odd

        # 'password' identifier starts inside quotes
        pwd_idx = sql_line.find("password")
        assert is_index_inside_quote(sql_line, pwd_idx)

        # Scanning this code snippet should produce NO secret findings (SEC-SECRET-002)
        findings = scan_security_issues(sql_line, "auth.py")
        secret_findings = [f for f in findings if f["rule_id"] == "SEC-SECRET-002"]
        assert len(secret_findings) == 0

    def test_genuine_secret_still_detected(self):
        line = 'JWT_SECRET_KEY = "my_super_secret_jwt_key_98765"'
        pwd_idx = line.find("JWT_SECRET_KEY")
        assert not is_index_inside_quote(line, pwd_idx)

        findings = scan_security_issues(line, "auth.py")
        secret_findings = [f for f in findings if f["rule_id"] == "SEC-SECRET-002"]
        assert len(secret_findings) == 1
        assert "[REDACTED]" in secret_findings[0]["matched_code"]
        assert "my_super_secret_jwt_key_98765" not in secret_findings[0]["matched_code"]


class TestBacktickSecretDetectionAndRedaction:
    def test_backtick_constant_secret_redacted(self):
        line = "const API_KEY = `sk_live_synthetic_api_key_12345`;"
        redacted = redact_sensitive_line(line)
        assert "sk_live_synthetic_api_key_12345" not in redacted
        assert "`[REDACTED]`" in redacted or '"[REDACTED]"' in redacted

        findings = scan_security_issues(line, "config.ts")
        secret_findings = [f for f in findings if f["rule_id"] == "SEC-SECRET-002"]
        assert len(secret_findings) == 1
        assert "sk_live_synthetic_api_key_12345" not in secret_findings[0]["matched_code"]

    def test_backtick_interpolated_secret_redacted(self):
        line = "const JWT_SECRET_KEY = `secret_${process.env.APP_ENV}_val`;"
        redacted = redact_sensitive_line(line)
        assert "secret_${process.env.APP_ENV}_val" not in redacted
        assert "[REDACTED]" in redacted

    def test_backtick_short_secret_redacted(self):
        line = "const DATABASE_PASSWORD = `short`;"
        redacted = redact_sensitive_line(line)
        assert "`short`" not in redacted
        assert "[REDACTED]" in redacted

    def test_backtick_in_container_single_line(self):
        line = "api_tokens = [`synth_token_alpha`, `synth_token_beta`]"
        redacted = redact_sensitive_line(line)
        assert "synth_token_alpha" not in redacted
        assert "synth_token_beta" not in redacted
        assert "[REDACTED]" in redacted

    def test_non_sensitive_backtick_string_not_flagged_or_corrupted(self):
        line = "const GREETING = `Hello, ${user.name}! Welcome back.`;"
        redacted = redact_sensitive_line(line)
        assert redacted == line

        findings = scan_security_issues(line, "greet.ts")
        secret_findings = [f for f in findings if f["rule_id"] == "SEC-SECRET-002"]
        assert len(secret_findings) == 0

    def test_backtick_multiline_container_diff_redaction(self):
        raw_diff = (
            "diff --git a/app.ts b/app.ts\n"
            "index 1234567..89abcdef 100644\n"
            "--- a/app.ts\n"
            "+++ b/app.ts\n"
            "@@ -1,5 +1,5 @@\n"
            "-api_keys = [\n"
            "-    `old_leak_synthetic_1`,\n"
            "-    `old_leak_synthetic_2`\n"
            "-]\n"
            "+api_keys = [\n"
            "+    `new_leak_synthetic_1`,\n"
            "+    `new_leak_synthetic_2`\n"
            "+]\n"
        )
        sanitized = sanitize_diff_content(raw_diff)
        assert "old_leak_synthetic_1" not in sanitized
        assert "old_leak_synthetic_2" not in sanitized
        assert "new_leak_synthetic_1" not in sanitized
        assert "new_leak_synthetic_2" not in sanitized
        assert "[REDACTED]" in sanitized
