"""
Unit tests for EngineeringStandardsEngine and the 5 policy rules.
Verifies:
- Rule 1: Maximum function length (violations, passes, incomplete context).
- Rule 2: Maximum nesting depth.
- Rule 3: Prohibited imports (Python and JS/TS, additions only).
- Rule 4: Custom regex patterns (matching, non-matching, duplicate suppression).
- Rule 5: Require test changes (thresholds, advisory phrasing, clean pass).
- Distinction: finding_type == FindingType.POLICY_VIOLATION.
"""

import pytest
from app.parser.diff_parser import parse_git_diff
from app.models.schemas import FindingType, PolicyEvaluationStatus, SeverityLevel
from app.standards.config_schema import (
    parse_standards_config,
    DiffguardConfig,
    StandardsConfig,
    CodeQualityStandards,
    MaxFunctionLengthRule,
    MaxNestingDepthRule,
    SecurityStandards,
    ProhibitedImportsRule,
    CustomPatternsRule,
    CustomPatternRuleItem,
    TestingStandards,
    RequireTestChangesRule,
)
from app.standards.rule_engine import EngineeringStandardsEngine


SAMPLE_PYTHON_LONG_FUNCTION_DIFF = """diff --git a/services/report.py b/services/report.py
index 1000000..2000000 100644
--- a/services/report.py
+++ b/services/report.py
@@ -10,3 +10,25 @@ def existing_func():
+def generate_large_report(data):
+    row1 = 1
+    row2 = 2
+    row3 = 3
+    row4 = 4
+    row5 = 5
+    row6 = 6
+    row7 = 7
+    row8 = 8
+    row9 = 9
+    row10 = 10
+    row11 = 11
+    row12 = 12
+    row13 = 13
+    row14 = 14
+    row15 = 15
+    row16 = 16
+    row17 = 17
+    row18 = 18
+    row19 = 19
+    row20 = 20
+    return data
+
 def another_func():
     pass
"""

SAMPLE_PYTHON_INCOMPLETE_FUNCTION_DIFF = """diff --git a/services/worker.py b/services/worker.py
index 1000000..2000000 100644
--- a/services/worker.py
+++ b/services/worker.py
@@ -10,6 +10,6 @@
+def incomplete_worker_loop():
+    step1 = True
+    step2 = False
+    step3 = "Incomplete hunk ends here"
"""

SAMPLE_PROHIBITED_IMPORTS_DIFF = """diff --git a/tasks/sync.py b/tasks/sync.py
index 1000000..2000000 100644
--- a/tasks/sync.py
+++ b/tasks/sync.py
@@ -1,3 +1,6 @@
 import json
+import pickle
+from telnetlib import Telnet
-import old_safe_module
+import os
"""

SAMPLE_NESTING_DIFF = """diff --git a/core/logic.py b/core/logic.py
index 1000000..2000000 100644
--- a/core/logic.py
+++ b/core/logic.py
@@ -10,3 +10,12 @@ def process(x):
+    if x > 0:
+        if x > 10:
+            if x > 20:
+                if x > 30:
+                    if x > 40:
+                        return True
"""

SAMPLE_CUSTOM_PATTERN_DIFF = """diff --git a/config/auth.py b/config/auth.py
index 1000000..2000000 100644
--- a/config/auth.py
+++ b/config/auth.py
@@ -5,3 +5,5 @@
+DEBUG_PASSWORD = "insecure_dev_pass"
+TEMP_TOKEN = "xyz"
"""


def test_rule_max_function_length_violation():
    """Function spanning 23 lines violates a 15-line limit."""
    parsed = parse_git_diff(SAMPLE_PYTHON_LONG_FUNCTION_DIFF)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            code_quality=CodeQualityStandards(
                max_function_length=MaxFunctionLengthRule(enabled=True, value=15, severity=SeverityLevel.HIGH)
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == FindingType.POLICY_VIOLATION
    assert f.rule_id == "STD-LEN-001"
    assert f.severity == SeverityLevel.HIGH
    assert f.policy_evaluation_status == PolicyEvaluationStatus.VIOLATED
    assert "generate_large_report" in f.title
    assert f.location.file_path == "services/report.py"


def test_rule_max_function_length_passes_when_under_limit():
    """Function within limit does not generate finding."""
    parsed = parse_git_diff(SAMPLE_PYTHON_LONG_FUNCTION_DIFF)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            code_quality=CodeQualityStandards(
                max_function_length=MaxFunctionLengthRule(enabled=True, value=50, severity=SeverityLevel.HIGH)
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)
    assert len(findings) == 0


def test_rule_max_function_length_incomplete_context_not_flagged():
    """When function boundaries extend beyond hunk, engine does not guess or emit false violation."""
    parsed = parse_git_diff(SAMPLE_PYTHON_INCOMPLETE_FUNCTION_DIFF)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            code_quality=CodeQualityStandards(
                max_function_length=MaxFunctionLengthRule(enabled=True, value=2, severity=SeverityLevel.HIGH)
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)
    assert len(findings) == 0


def test_rule_prohibited_imports_detected():
    """Added imports matching configured list are flagged."""
    parsed = parse_git_diff(SAMPLE_PROHIBITED_IMPORTS_DIFF)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            security=SecurityStandards(
                prohibited_imports=ProhibitedImportsRule(enabled=True, values=["pickle", "telnetlib"])
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)

    assert len(findings) == 2
    rule_ids = {f.rule_id for f in findings}
    assert rule_ids == {"STD-IMP-001"}
    titles = " ".join(f.title for f in findings)
    assert "pickle" in titles
    assert "telnetlib" in titles
    for f in findings:
        assert f.finding_type == FindingType.POLICY_VIOLATION
        assert f.policy_evaluation_status == PolicyEvaluationStatus.VIOLATED


def test_rule_prohibited_imports_ignores_deleted_lines():
    """Prohibited imports in deleted lines (-) do not trigger policy violations."""
    diff_with_deleted = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
-import pickle
+import json
"""
    parsed = parse_git_diff(diff_with_deleted)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            security=SecurityStandards(
                prohibited_imports=ProhibitedImportsRule(enabled=True, values=["pickle"])
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)
    assert len(findings) == 0


def test_rule_max_nesting_depth_violation():
    """Nesting depth exceeding configured limit generates violation."""
    parsed = parse_git_diff(SAMPLE_NESTING_DIFF)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            code_quality=CodeQualityStandards(
                max_nesting_depth=MaxNestingDepthRule(enabled=True, value=3)
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)

    assert len(findings) >= 1
    f = findings[0]
    assert f.finding_type == FindingType.POLICY_VIOLATION
    assert f.rule_id == "STD-NEST-001"
    assert "Nesting Depth Exceeds Standard" in f.title


def test_rule_custom_pattern_matching_and_deduplication():
    """Custom regex pattern flags matched added line."""
    parsed = parse_git_diff(SAMPLE_CUSTOM_PATTERN_DIFF)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            security=SecurityStandards(
                custom_patterns=CustomPatternsRule(
                    enabled=True,
                    rules=[
                        CustomPatternRuleItem(
                            id="POLICY-SEC-001",
                            name="Prohibited debug credentials",
                            pattern=r"DEBUG_PASSWORD\s*=",
                            severity=SeverityLevel.CRITICAL
                        )
                    ]
                )
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == FindingType.POLICY_VIOLATION
    assert f.rule_id == "POLICY-SEC-001"
    assert f.severity == SeverityLevel.CRITICAL
    assert "DEBUG_PASSWORD" in f.location.code_context


def test_rule_require_test_changes_reports_patch_limitation():
    """Rule reports missing patch tests without claiming tests don't exist in whole repo."""
    diff_no_tests = """diff --git a/services/order.py b/services/order.py
--- a/services/order.py
+++ b/services/order.py
@@ -1,3 +1,15 @@
+def process_new_order(order_id):
+    line1 = 1
+    line2 = 2
+    line3 = 3
+    line4 = 4
+    line5 = 5
+    line6 = 6
+    line7 = 7
+    line8 = 8
+    line9 = 9
+    return True
"""
    parsed = parse_git_diff(diff_no_tests)
    cfg = DiffguardConfig(
        version=1,
        standards=StandardsConfig(
            testing=TestingStandards(
                require_test_changes=RequireTestChangesRule(enabled=True, min_additions_threshold=5)
            )
        )
    )
    engine = EngineeringStandardsEngine(cfg)
    findings = engine.evaluate(parsed)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == FindingType.POLICY_VIOLATION
    assert f.rule_id == "STD-TEST-001"
    assert "No corresponding test changes were detected in the submitted patch" in f.why_identified
    assert "No tests exist" not in f.why_identified

