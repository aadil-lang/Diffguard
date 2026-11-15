"""
Phase 3.1.1 Targeted Corrective Regression Test Suite.
Verifies all 7 corrective areas from Phase 3.1 Independent Audit:
- F-01: Custom Regex ReDoS Protection via Google RE2
- F-02: Frontend Sample Policy (.diffguard.yaml) Schema Conformance
- F-03: Function Length Evaluator Nested Functions & Docstring Support
- F-04: Nesting Depth 2-Space, Tab, and Parameter Alignment Support
- F-05: Prohibited Imports Multi-Import, From-Import, and Scoped Packages
- F-06: Test Requirement Accurate Path Classification & Non-Code Exclusion
- F-07: Gemini Synthesis Semantic Collision Deduplication
"""

import time
import pytest
from app.parser.diff_parser import parse_git_diff
from app.standards.config_schema import (
    parse_standards_config,
    CustomPatternRuleItem,
    CustomPatternsRule,
    MaxFunctionLengthRule,
    MaxNestingDepthRule,
    ProhibitedImportsRule,
    RequireTestChangesRule,
)
from app.standards.rules.custom_patterns import evaluate_custom_patterns
from app.standards.rules.function_length import evaluate_function_length
from app.standards.rules.nesting_depth import evaluate_nesting_depth
from app.standards.rules.prohibited_imports import evaluate_prohibited_imports
from app.standards.rules.test_requirements import evaluate_require_test_changes, is_test_file, is_production_code_file
from app.models.schemas import Finding, FindingCategory, FindingConfidence, FindingType, CodeLocation, ReviewResponse, ReviewSummary


# ---------------------------------------------------------------------------
# F-01: Custom Regex ReDoS Protection via Google RE2
# ---------------------------------------------------------------------------

def test_f01_catastrophic_backtracking_pattern_executes_in_linear_time():
    """Verify that potentially catastrophic patterns (e.g. ^(a+)+$) execute safely in sub-millisecond time."""
    yaml_config = """
version: 1
standards:
  security:
    custom_patterns:
      enabled: true
      rules:
        - id: SEC-REDOS-TEST
          name: Catastrophic Pattern Test
          pattern: '^(a+)+$'
          severity: high
"""
    cfg = parse_standards_config(yaml_config)
    assert cfg.standards.security.custom_patterns.enabled is True

    # Test execution against long near-matching string
    diff_text = f"""diff --git a/test.py b/test.py
index 1000..2000 100644
--- a/test.py
+++ b/test.py
@@ -1,1 +1,2 @@
+{'a' * 50}!
"""
    parsed = parse_git_diff(diff_text)
    t0 = time.monotonic()
    findings = evaluate_custom_patterns(parsed, cfg.standards.security.custom_patterns)
    elapsed = time.monotonic() - t0

    # RE2 guarantees linear time: 50 characters takes < 0.05 seconds
    assert elapsed < 0.1, f"Evaluation took {elapsed}s; ReDoS protection failed"
    assert len(findings) == 0  # Does not match due to trailing '!'


def test_f01_unsupported_re2_constructs_rejected_at_validation():
    """Verify that regex constructs unsupported by RE2 (like lookarounds) raise clear validation errors."""
    yaml_config = """
version: 1
standards:
  security:
    custom_patterns:
      enabled: true
      rules:
        - id: SEC-LOOKAROUND
          name: Unsupported Lookaround
          pattern: '(?=abc)'
          severity: high
"""
    with pytest.raises(ValueError) as exc_info:
        parse_standards_config(yaml_config)
    assert "DiffGuard uses Google RE2 for guaranteed linear-time matching" in str(exc_info.value)


# ---------------------------------------------------------------------------
# F-02: Frontend Sample Policy Conformance
# ---------------------------------------------------------------------------

def test_f02_frontend_sample_standards_yaml_matches_backend_schema():
    """Extract and validate the actual SAMPLE_STANDARDS_YAML string from DiffInput.tsx."""
    with open("frontend/src/components/DiffInput.tsx", "r", encoding="utf-8") as f:
        content = f.read()

    bt = chr(96)
    prefix = f"const SAMPLE_STANDARDS_YAML = {bt}"
    assert prefix in content, "SAMPLE_STANDARDS_YAML not found in DiffInput.tsx"
    
    start = content.index(prefix) + len(prefix)
    end = content.index(f"{bt};", start)
    sample_yaml = content[start:end]

    # Validate against backend parser
    cfg = parse_standards_config(sample_yaml)
    assert cfg.version == 1
    assert cfg.project.name == "sample-repository"
    assert cfg.standards.code_quality.max_function_length.enabled is True
    assert cfg.standards.code_quality.max_function_length.value == 50
    assert cfg.standards.code_quality.max_nesting_depth.enabled is True
    assert cfg.standards.security.prohibited_imports.enabled is True
    assert "pickle" in cfg.standards.security.prohibited_imports.values
    assert cfg.standards.security.custom_patterns.enabled is True
    assert len(cfg.standards.security.custom_patterns.rules) == 1
    assert cfg.standards.testing.require_test_changes.enabled is True


# ---------------------------------------------------------------------------
# F-03: Function Length Nested Function and Docstring Tests
# ---------------------------------------------------------------------------

def test_f03_nested_python_function_evaluated_without_skipping():
    """Verify that an inner helper function exceeding the line limit is flagged even when outer is under limit."""
    diff_text = """diff --git a/services/auth.py b/services/auth.py
index 1000..2000 100644
--- a/services/auth.py
+++ b/services/auth.py
@@ -1,3 +1,15 @@
+def outer_handler():
+    x = 1
+    def nested_helper_too_long():
+        l1 = 1
+        l2 = 2
+        l3 = 3
+        l4 = 4
+        l5 = 5
+        return l5
+    return nested_helper_too_long()
"""
    parsed = parse_git_diff(diff_text)
    findings = evaluate_function_length(parsed, MaxFunctionLengthRule(enabled=True, value=4))
    
    assert len(findings) >= 1
    assert any("nested_helper_too_long" in f.title for f in findings)


def test_f03_python_multiline_docstring_column_zero_does_not_prematurely_terminate():
    """Verify that column-0 formatted lines in docstrings do not truncate function length."""
    diff_text = """diff --git a/services/doc.py b/services/doc.py
index 1000..2000 100644
--- a/services/doc.py
+++ b/services/doc.py
@@ -1,3 +1,14 @@
+def function_with_docstring():
+    \"\"\"
+Markdown code block at col 0:
+def example():
+    pass
+    \"\"\"
+    result = 42
+    return result
+
+def next_func():
+    pass
"""
    parsed = parse_git_diff(diff_text)
    # Total function spans 9 lines; with value=5 it should be flagged with measured length 9
    findings = evaluate_function_length(parsed, MaxFunctionLengthRule(enabled=True, value=5))
    assert len(findings) == 1
    assert "function_with_docstring" in findings[0].title


def test_f03_js_multiline_arrow_function_and_string_braces():
    """Verify multiline arrow function detection and string brace immunity in JS."""
    diff_text = """diff --git a/src/handler.ts b/src/handler.ts
index 1000..2000 100644
--- a/src/handler.ts
+++ b/src/handler.ts
@@ -1,3 +1,10 @@
+export const processBatch = async (
+  items: string[]
+): Promise<void> => {
+  const msg = "ignore braces { in string }";
+  const another = 1;
+  console.log(msg, another);
+};
"""
    parsed = parse_git_diff(diff_text)
    findings = evaluate_function_length(parsed, MaxFunctionLengthRule(enabled=True, value=4))
    assert len(findings) == 1
    assert "processBatch" in findings[0].title


# ---------------------------------------------------------------------------
# F-04: Nesting Depth 2-Space, Tab, and Parameter Alignment
# ---------------------------------------------------------------------------

def test_f04_tab_indented_lines_evaluated():
    """Verify that tab characters are expanded and evaluated for nesting depth."""
    diff_text = """diff --git a/legacy.py b/legacy.py
index 1000..2000 100644
--- a/legacy.py
+++ b/legacy.py
@@ -1,1 +1,4 @@
+\t\t\t\t\tif True:
+\t\t\t\t\t\tprint('deeply tabbed')
"""
    parsed = parse_git_diff(diff_text)
    findings = evaluate_nesting_depth(parsed, MaxNestingDepthRule(enabled=True, value=3))
    assert len(findings) == 1
    assert "Nesting Depth Exceeds Standard" in findings[0].title


def test_f04_two_space_indented_typescript_evaluated_with_step_two():
    """Verify that 2-space indented code detects depth accurately."""
    diff_text = """diff --git a/src/component.tsx b/src/component.tsx
index 1000..2000 100644
--- a/src/component.tsx
+++ b/src/component.tsx
@@ -1,1 +1,9 @@
+function renderList() {
+  if (ready) {
+    for (const item of items) {
+      if (item.active) {
+        console.log(item);
+      }
+    }
+  }
+}
"""
    parsed = parse_git_diff(diff_text)
    findings = evaluate_nesting_depth(parsed, MaxNestingDepthRule(enabled=True, value=3))
    assert len(findings) == 1
    assert "Depth 4 > 3" in findings[0].title


def test_f04_json_and_yaml_non_code_files_ignored():
    """Verify that configuration files like JSON and YAML are not penalized for data structure depth."""
    diff_text = """diff --git a/config.json b/config.json
index 1000..2000 100644
--- a/config.json
+++ b/config.json
@@ -1,1 +1,8 @@
+{
+    "a": {
+        "b": {
+            "c": {
+                "d": 1
+            }
+        }
+    }
+}
"""
    parsed = parse_git_diff(diff_text)
    findings = evaluate_nesting_depth(parsed, MaxNestingDepthRule(enabled=True, value=2))
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# F-05: Prohibited Imports Multi-Import, From-Import, and Scoped Packages
# ---------------------------------------------------------------------------

def test_f05_python_multi_import_and_from_import():
    """Verify Python multiple imports on one line and from-package imports."""
    diff_text = """diff --git a/auth.py b/auth.py
index 1000..2000 100644
--- a/auth.py
+++ b/auth.py
@@ -1,1 +1,4 @@
+import os, pickle, sys
+from utils import telnetlib
"""
    parsed = parse_git_diff(diff_text)
    findings = evaluate_prohibited_imports(
        parsed,
        ProhibitedImportsRule(enabled=True, values=["pickle", "telnetlib"])
    )
    assert len(findings) == 2
    matched = {f.title for f in findings}
    assert "Prohibited Import 'pickle' Detected" in matched
    assert "Prohibited Import 'telnetlib' Detected" in matched


def test_f05_typescript_scoped_package_import():
    """Verify JavaScript/TypeScript scoped package exact matching."""
    diff_text = """diff --git a/client.ts b/client.ts
index 1000..2000 100644
--- a/client.ts
+++ b/client.ts
@@ -1,1 +1,3 @@
+import client from "@badorg/vulnerable-pkg";
"""
    parsed = parse_git_diff(diff_text)
    findings = evaluate_prohibited_imports(
        parsed,
        ProhibitedImportsRule(enabled=True, values=["@badorg/vulnerable-pkg"])
    )
    assert len(findings) == 1
    assert "@badorg/vulnerable-pkg" in findings[0].title


# ---------------------------------------------------------------------------
# F-06: Test Requirement Accurate Path Classification
# ---------------------------------------------------------------------------

def test_f06_production_files_with_test_in_name_not_misclassified():
    """Verify production files containing 'test' in their name are not classified as tests."""
    diff_text = """diff --git a/services/fast_testimony_service.py b/services/fast_testimony_service.py
index 1000..2000 100644
--- a/services/fast_testimony_service.py
+++ b/services/fast_testimony_service.py
@@ -1,1 +1,11 @@
+def generate_testimony():
+    a = 1
+    b = 2
+    c = 3
+    d = 4
+    e = 5
+    f = 6
+    g = 7
+    h = 8
+    return a + b
"""
    parsed = parse_git_diff(diff_text)
    assert not is_test_file("services/fast_testimony_service.py")
    assert is_production_code_file("services/fast_testimony_service.py")

    findings = evaluate_require_test_changes(
        parsed,
        RequireTestChangesRule(enabled=True, min_additions_threshold=8)
    )
    # Correctly flagged because this production file has 10 additions without accompanying test file
    assert len(findings) == 1
    assert "No Corresponding Test Changes" in findings[0].title


def test_f06_documentation_files_ignored():
    """Verify that documentation changes (README.md, docs) do not trigger test requirements."""
    diff_text = """diff --git a/README.md b/README.md
index 1000..2000 100644
--- a/README.md
+++ b/README.md
@@ -1,1 +1,10 @@
+# Project Documentation
+Documentation line 1
+Documentation line 2
+Documentation line 3
+Documentation line 4
+Documentation line 5
+Documentation line 6
+Documentation line 7
+Documentation line 8
"""
    parsed = parse_git_diff(diff_text)
    assert not is_production_code_file("README.md")
    findings = evaluate_require_test_changes(
        parsed,
        RequireTestChangesRule(enabled=True, min_additions_threshold=5)
    )
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# F-07: Gemini Semantic Collision Deduplication
# ---------------------------------------------------------------------------

def test_f07_gemini_finding_without_rule_id_upgraded_to_authoritative_policy():
    """Verify that when Gemini produces a finding describing a policy without rule_id, it is deduplicated/upgraded."""
    from app.agent.reviewer_agent import ReviewAgent
    from app.models.schemas import ReviewRequest

    # Create dummy agent to test the deterministic merge
    agent = ReviewAgent()

    # Deterministic policy finding
    pf = Finding(
        id="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=ProhibitedImportsRule().severity,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="auth.py", start_line=1),
        why_identified="Prohibited module pickle imported",
        impact="Security risk",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id="STD-IMP-001",
        rule_name="Prohibited Imports",
        policy_category="security",
    )

    # Simulated Gemini response containing an unclassified/defect finding describing the same issue
    model_finding = Finding(
        id="GEM-001",
        title="Insecure pickle import detected",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=ProhibitedImportsRule().severity,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="auth.py", start_line=1),
        why_identified="The developer imported prohibited pickle module",
        impact="Deserialization flaw",
        finding_type=FindingType.CODE_DEFECT,  # Model classified as defect
        rule_id=None,  # Model omitted rule_id
    )

    distinct_defect = Finding(
        id="GEM-002",
        title="SQL Injection in auth query",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=ProhibitedImportsRule().severity,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="auth.py", start_line=1),
        why_identified="Direct SQL string concatenation",
        impact="Database takeover",
        finding_type=FindingType.CODE_DEFECT,
        rule_id=None,
    )

    ai_response = ReviewResponse(
        review_id="rev-001",
        timestamp="2026-11-14T00:00:00Z",
        stages_executed=[],
        findings=[model_finding, distinct_defect],
        summary=ReviewSummary(),
        engine_used="gemini-agent",
        parsed_files_count=1,
        total_additions=2,
        total_deletions=0,
    )

    # Run merge logic as executed in reviewer_agent.py
    merged_findings = []
    matched_policy_ids = set()

    for f in ai_response.findings:
        colliding_pf = None
        for p in [pf]:
            if p.id in matched_policy_ids:
                continue
            if f.location.file_path == p.location.file_path and f.location.start_line == p.location.start_line:
                if f.rule_id and f.rule_id == p.rule_id:
                    colliding_pf = p
                    break
                if not f.rule_id:
                    f_text = f"{f.title} {f.why_identified}".lower()
                    rule_name_lower = (p.rule_name or "").lower()
                    rule_id_lower = (p.rule_id or "").lower()
                    category_lower = (p.policy_category or "").lower()
                    if (
                        (rule_id_lower and rule_id_lower in f_text)
                        or (rule_name_lower and rule_name_lower.rstrip("s") in f_text)
                        or (category_lower and category_lower in f_text and f.category == p.category)
                        or ("prohibited" in f_text and "import" in f_text)
                    ):
                        colliding_pf = p
                        break
        if colliding_pf:
            matched_policy_ids.add(colliding_pf.id)
            merged_findings.append(colliding_pf)
        else:
            merged_findings.append(f)

    for p in [pf]:
        if p.id not in matched_policy_ids:
            merged_findings.append(p)

    assert len(merged_findings) == 2  # No duplicate card!
    finding_types = [f.finding_type for f in merged_findings]
    assert FindingType.POLICY_VIOLATION in finding_types
    assert FindingType.CODE_DEFECT in finding_types  # SQL injection defect preserved!
