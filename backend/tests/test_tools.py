"""
Unit tests for DiffGuard Agent Tools: Security Scanner, Syntax Checker, Complexity Analyzer, Test Coverage Analyzer.
"""

from app.tools.security_scanner import scan_security_issues
from app.tools.syntax_checker import run_syntax_and_linter_checks
from app.tools.complexity_analyzer import analyze_complexity
from app.tools.test_requirement_analyzer import analyze_test_coverage
from app.parser.diff_parser import parse_git_diff
from app.samples.sample_diffs import SAMPLE_UNTESTED_COMPLEXITY, SAMPLE_CLEAN_PR


def test_security_scanner_detects_sqli():
    code = '+ cursor.execute(f"SELECT * FROM users WHERE email = \'{user_email}\'")'
    findings = scan_security_issues(code, "services/auth.py")
    assert len(findings) >= 1
    assert any(f["rule_id"] == "SEC-SQLI-001" for f in findings)
    assert findings[0]["severity"] == "CRITICAL"


def test_security_scanner_detects_hardcoded_secret():
    code = '+ JWT_SECRET = "super_secret_jwt_key_1234567890abcdef"'
    findings = scan_security_issues(code, "config.py")
    assert len(findings) >= 1
    assert any(f["rule_id"] == "SEC-SECRET-002" for f in findings)


def test_security_scanner_detects_command_injection():
    code = '+ subprocess.call("rm -rf " + user_input, shell=True)'
    findings = scan_security_issues(code, "utils/cleaner.py")
    assert len(findings) >= 1
    assert any(f["rule_id"] == "SEC-CMD-003" for f in findings)


def test_syntax_checker_python_bare_except():
    code = """
+ try:
+     do_risky_io()
+ except:
+     pass
"""
    findings = run_syntax_and_linter_checks(code, "worker.py", "python")
    assert len(findings) >= 1
    assert any(f["type"] == "BARE_EXCEPT" for f in findings)


def test_syntax_checker_js_loose_equality():
    code = '+ if (status == 200) { return true; }'
    findings = run_syntax_and_linter_checks(code, "client.ts", "typescript")
    assert len(findings) >= 1
    assert any(f["type"] == "LOOSE_EQUALITY" for f in findings)


def test_complexity_analyzer():
    nested_code = """
+ if a > 0:
+     if b > 1:
+         if c > 2:
+             if d > 3:
+                 if e > 4:
+                     return True
"""
    res = analyze_complexity(nested_code, "logic.py")
    assert res["max_nesting_depth"] >= 5
    assert res["risk_level"] in ("HIGH", "MEDIUM")
    assert res["warning"] is not None


def test_test_coverage_analyzer_flags_untested_production():
    parsed = parse_git_diff(SAMPLE_UNTESTED_COMPLEXITY.diff_content)
    test_issues = analyze_test_coverage(parsed)
    assert len(test_issues) >= 1
    assert "rebate_calculator.py" in test_issues[0]["file_path"]


def test_test_coverage_analyzer_passes_tested_pr():
    parsed = parse_git_diff(SAMPLE_CLEAN_PR.diff_content)
    test_issues = analyze_test_coverage(parsed)
    # The clean PR includes tests/test_rate_limiter.py, so it should not flag missing test coverage
    assert len(test_issues) == 0

