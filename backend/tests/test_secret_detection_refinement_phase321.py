"""
Regression and Verification Tests for Phase 3.2.1:
Deterministic Security Scanner Refinement (SEC-SECRET-002) for Compound Credential Names.
"""

import pytest
from app.tools.security_scanner import scan_security_issues
from app.parser.diff_parser import parse_git_diff
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH, SAMPLE_CLEAN_PR
from app.models.schemas import ReviewRequest, LineSide, SeverityLevel
from app.agent.reviewer_agent import ReviewAgent


class TestCompoundSecretDetection:
    """Category A: Previously missed compound secret names."""

    def test_detects_jwt_secret_key(self):
        code = '+ JWT_SECRET_KEY = "prod_jwt_super_secret_key_diffguard_9876543210"'
        findings = scan_security_issues(code, "services/auth_service.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"
        assert findings[0]["severity"] == "CRITICAL"
        assert "JWT_SECRET_KEY" in findings[0]["matched_code"]

    def test_detects_aws_secret_key(self):
        code = '+ AWS_SECRET_KEY = "AKIAIOSFODNN7EXAMPLE12345"'
        findings = scan_security_issues(code, "config/aws.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_database_password(self):
        code = '+ DATABASE_PASSWORD = "super_secret_db_pass_123456"'
        findings = scan_security_issues(code, "database/settings.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_api_token(self):
        code = '+ API_TOKEN = "github_pat_11AAAAAAA0123456789abcdef"'
        findings = scan_security_issues(code, "integrations/github.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_private_key(self):
        code = '+ PRIVATE_KEY = "rsa_priv_key_9876543210abcdef"'
        findings = scan_security_issues(code, "security/crypto.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"


class TestExistingSecretDetectionPreserved:
    """Category B: Backward compatibility with previously supported formats."""

    def test_detects_jwt_secret_without_key_suffix(self):
        code = '+ JWT_SECRET = "super_secret_jwt_key_1234567890abcdef"'
        findings = scan_security_issues(code, "config.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_simple_api_key(self):
        code = '+ api_key = "1234567890123456"'
        findings = scan_security_issues(code, "client.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_simple_token(self):
        code = '+ token = "abcdef1234567890"'
        findings = scan_security_issues(code, "session.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_simple_password(self):
        code = '+ password = "secret_password_12345"'
        findings = scan_security_issues(code, "auth.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_standalone_secret(self):
        code = '+ SECRET = "very_long_secret_value_12345"'
        findings = scan_security_issues(code, "settings.py")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"

    def test_detects_colon_assignment_in_yaml_or_json(self):
        code = '+ client_secret: "prod_client_secret_value_98765"'
        findings = scan_security_issues(code, "config.yaml")
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "SEC-SECRET-002"


class TestFalsePositiveResistance:
    """Category C: Non-secret variables must never trigger SEC-SECRET-002."""

    def test_ignores_user_key(self):
        code = '+ user_key = "customer_reference_value_12345"'
        findings = scan_security_issues(code, "models/user.py")
        assert len(findings) == 0

    def test_ignores_keyboard_layout(self):
        code = '+ keyboard_layout = "qwerty"'
        findings = scan_security_issues(code, "ui/settings.py")
        assert len(findings) == 0

    def test_ignores_token_count_integer(self):
        code = '+ token_count = 10'
        findings = scan_security_issues(code, "parser/tokens.py")
        assert len(findings) == 0

    def test_ignores_secret_mode_enabled_boolean(self):
        code = '+ secret_mode_enabled = True'
        findings = scan_security_issues(code, "config/features.py")
        assert len(findings) == 0

    def test_ignores_public_key_name(self):
        code = '+ public_key_name = "default"'
        findings = scan_security_issues(code, "crypto/keys.py")
        assert len(findings) == 0

    def test_ignores_cache_and_sort_keys(self):
        code = """
+ cache_key = "cache_prefix_item_12345"
+ sort_key = "sort_by_created_at_12345"
+ primary_key = "id_column_identifier_12345"
+ foreign_key = "user_id_column_ref_12345"
+ item_key = "item_lookup_key_reference_12345"
"""
        findings = scan_security_issues(code, "db/cache.py")
        assert len(findings) == 0


class TestEvidenceAndLocationIntegrity:
    """Category D: Line numbers, diff side, and context integrity."""

    def test_scenario_a_end_to_end_detects_all_three_defects(self):
        agent = ReviewAgent()
        req = ReviewRequest(
            diff_content=SAMPLE_SQLI_AUTH.diff_content,
            title=SAMPLE_SQLI_AUTH.title
        )
        response = agent.execute_review(req)

        assert response.summary.verdict == "CRITICAL_BLOCKER"
        assert len(response.findings) == 3

        # 1. SQL Injection
        sqli = next((f for f in response.findings if "SQL Injection" in f.title), None)
        assert sqli is not None
        assert sqli.severity == SeverityLevel.CRITICAL
        assert sqli.location.file_path == "services/auth_service.py"
        assert sqli.location.start_line == 24
        assert sqli.location.line_side == LineSide.NEW

        # 2. Hardcoded Secret (Now Detected!)
        secret = next((f for f in response.findings if "Hardcoded Secret" in f.title), None)
        assert secret is not None
        assert secret.severity == SeverityLevel.CRITICAL
        assert secret.location.file_path == "services/auth_service.py"
        assert secret.location.start_line == 15
        assert secret.location.line_side == LineSide.NEW
        assert "JWT_SECRET_KEY" in (secret.location.code_context or "")

        # 3. Missing Tests
        tests = next((f for f in response.findings if "Untested Production" in f.title), None)
        assert tests is not None
        assert tests.location.line_side == LineSide.FILE_LEVEL

    def test_scenario_b_remains_clean(self):
        agent = ReviewAgent()
        req = ReviewRequest(
            diff_content=SAMPLE_CLEAN_PR.diff_content,
            title=SAMPLE_CLEAN_PR.title
        )
        response = agent.execute_review(req)
        assert response.summary.verdict in ("APPROVED", "APPROVED_WITH_COMMENTS")
        assert len(response.findings) == 0

