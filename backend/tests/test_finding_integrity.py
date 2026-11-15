"""
Regression Test Suite for Workstream C: Finding Location Integrity.
Verifies that:
1. Model-generated findings are validated deterministically against diff hunks.
2. Deleted lines, added lines, context lines, and file-level scopes are accurately categorized.
3. Invalid or out-of-hunk line numbers are marked 'invalid' or 'unverified' and NEVER silently clamped.
4. Path normalizations (leading slashes, a/, b/ prefixes) resolve canonically.
"""

import pytest
from app.models.schemas import (
    Finding,
    CodeLocation,
    FindingCategory,
    SeverityLevel,
    FindingConfidence,
    LocationStatus,
    LineSide
)
from app.parser.diff_parser import parse_git_diff
from app.parser.location_validator import (
    DiffLocationIndex,
    validate_finding_location,
    validate_all_findings,
    normalize_repo_path
)
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH, SAMPLE_LOGIC_ASYNC_BUG


SAMPLE_MULTI_HUNK_DIFF = """diff --git a/services/payment.py b/services/payment.py
index 1000000..2000000 100644
--- a/services/payment.py
+++ b/services/payment.py
@@ -10,4 +10,5 @@ def validate_card(number: str):
     if len(number) < 16:
         return False
-    return True
+    # Added checksum verification
+    return luhn_check(number)
@@ -40,5 +41,5 @@ def process_charge(amount: float):
     if amount <= 0:
-        raise ValueError("Invalid amount")
+        raise ValueError("Amount must be positive")
     gateway.charge(amount)
"""


def test_path_normalization():
    assert normalize_repo_path("a/services/auth.py") == "services/auth.py"
    assert normalize_repo_path("b/services/auth.py") == "services/auth.py"
    assert normalize_repo_path("./services/auth.py") == "services/auth.py"
    assert normalize_repo_path('"services/auth.py"') == "services/auth.py"
    assert normalize_repo_path("'services/auth.py'") == "services/auth.py"
    assert normalize_repo_path('"a/services/auth.py"') == "services/auth.py"
    assert normalize_repo_path('"./services/auth.py"') == "services/auth.py"
    assert normalize_repo_path("/services/auth.py") == "services/auth.py"
    assert normalize_repo_path("services\\auth.py") == "services/auth.py"
    assert normalize_repo_path("  b/services/payment.py  ") == "services/payment.py"
    assert normalize_repo_path('  "b/my services/payment.py"  ') == "my services/payment.py"
    assert normalize_repo_path('"./my path/file with spaces.ts"') == "my path/file with spaces.ts"


def test_path_boundary_suffix_matching():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)
    # Target in patch is 'services/payment.py'
    # Suffix match on 'payment.py' should match 'services/payment.py'
    file_idx = index.find_file("payment.py")
    assert file_idx is not None
    assert file_idx.canonical_path == "services/payment.py"
    # Suffix without boundary ('repayment.py') must NOT match 'services/payment.py'
    assert index.find_file("repayment.py") is None


def test_valid_added_line_finding():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)

    # Line 13 in new file is the added luhn_check return
    finding = Finding(
        id="DG-TEST-001",
        title="Check added line",
        category=FindingCategory.BUG_OR_LOGIC_ERROR,
        severity=SeverityLevel.LOW,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(
            file_path="services/payment.py",
            start_line=13
        ),
        why_identified="Testing added line validation",
        impact="None"
    )

    validated = validate_finding_location(finding, index)
    assert validated.location.location_status == LocationStatus.VERIFIED
    assert validated.location.line_side == LineSide.NEW
    assert validated.location.start_line == 13  # Unchanged
    assert "Verified on added line 13" in (validated.location.validation_note or "")


def test_valid_deleted_line_finding():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)

    # Line 12 on old file is the deleted 'return True'
    finding = Finding(
        id="DG-TEST-002",
        title="Check deleted line",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(
            file_path="services/payment.py",
            start_line=12,
            line_side=LineSide.OLD
        ),
        why_identified="Testing deleted line validation",
        impact="None"
    )

    validated = validate_finding_location(finding, index)
    assert validated.location.location_status == LocationStatus.VERIFIED
    assert validated.location.line_side == LineSide.OLD
    assert validated.location.start_line == 12  # Unchanged
    assert "Verified on deleted line 12" in (validated.location.validation_note or "")


def test_valid_context_line_finding():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)

    # Line 10 is unchanged context 'def validate_card(number: str):'
    finding = Finding(
        id="DG-TEST-003",
        title="Check context line",
        category=FindingCategory.CODE_QUALITY_AND_MAINTAINABILITY,
        severity=SeverityLevel.INFO,
        confidence=FindingConfidence.IMPROVEMENT_SUGGESTION,
        location=CodeLocation(
            file_path="services/payment.py",
            start_line=10
        ),
        why_identified="Testing context line validation",
        impact="None"
    )

    validated = validate_finding_location(finding, index)
    assert validated.location.location_status == LocationStatus.VERIFIED
    assert validated.location.line_side == LineSide.BOTH


def test_file_level_finding():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)

    # Missing test coverage on the file
    finding = Finding(
        id="DG-TEST-004",
        title="Untested modifications",
        category=FindingCategory.MISSING_TEST_COVERAGE,
        severity=SeverityLevel.MEDIUM,
        confidence=FindingConfidence.POTENTIAL_ISSUE,
        location=CodeLocation(
            file_path="services/payment.py",
            start_line=0
        ),
        why_identified="No test files modified",
        impact="Regression risk"
    )

    validated = validate_finding_location(finding, index)
    assert validated.location.location_status == LocationStatus.FILE_LEVEL
    assert validated.location.line_side == LineSide.FILE_LEVEL


def test_unknown_file_path_marked_invalid():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)

    finding = Finding(
        id="DG-TEST-005",
        title="Hallucinated File Finding",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.CRITICAL,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(
            file_path="completely/nonexistent/service.py",
            start_line=45
        ),
        why_identified="Model hallucinated this file",
        impact="Critical"
    )

    validated = validate_finding_location(finding, index)
    assert validated.location.location_status == LocationStatus.INVALID
    assert "not found in the submitted patch" in (validated.location.validation_note or "")
    # Substantive finding content is strictly preserved
    assert validated.title == "Hallucinated File Finding"
    assert validated.location.start_line == 45  # Not clamped


def test_out_of_hunk_line_never_clamped():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)

    # Line 999 is outside all hunks (hunks are at 10-14 and 40-45).
    # Since the file exists in the patch, out-of-hunk line is UNVERIFIED (not INVALID),
    # preserving the original line without silent clamping.
    finding = Finding(
        id="DG-TEST-006",
        title="Out of Bounds Line Finding",
        category=FindingCategory.BUG_OR_LOGIC_ERROR,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(
            file_path="services/payment.py",
            start_line=999
        ),
        why_identified="Model reported out-of-hunk line",
        impact="High"
    )

    validated = validate_finding_location(finding, index)
    assert validated.location.location_status == LocationStatus.UNVERIFIED
    # MUST NOT be clamped to 45 or 14!
    assert validated.location.start_line == 999
    assert "outside patch hunks" in (validated.location.validation_note or "")


def test_negative_line_number_marked_invalid():
    parsed = parse_git_diff(SAMPLE_MULTI_HUNK_DIFF)
    index = DiffLocationIndex(parsed)

    finding = Finding(
        id="DG-TEST-NEG",
        title="Negative Line Finding",
        category=FindingCategory.BUG_OR_LOGIC_ERROR,
        severity=SeverityLevel.MEDIUM,
        confidence=FindingConfidence.POTENTIAL_ISSUE,
        location=CodeLocation(
            file_path="services/payment.py",
            start_line=-5
        ),
        why_identified="Model hallucinated negative line",
        impact="Low"
    )

    validated = validate_finding_location(finding, index)
    assert validated.location.location_status == LocationStatus.INVALID
    assert validated.location.start_line == -5
    assert "negative and invalid" in (validated.location.validation_note or "")


def test_path_prefix_variations_resolve_canonically():
    parsed = parse_git_diff(SAMPLE_SQLI_AUTH.diff_content)
    index = DiffLocationIndex(parsed)

    # Target in patch is 'services/auth_service.py'
    # Test submitting with 'b/services/auth_service.py'
    f1 = Finding(
        id="DG-TEST-007",
        title="Path Prefix Test",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.CRITICAL,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(
            file_path="b/services/auth_service.py",
            start_line=16
        ),
        why_identified="Testing prefix resolution",
        impact="High"
    )

    v1 = validate_finding_location(f1, index)
    assert v1.location.file_path == "services/auth_service.py"
    assert v1.location.location_status == LocationStatus.VERIFIED


def test_validate_all_findings_in_batch():
    parsed = parse_git_diff(SAMPLE_LOGIC_ASYNC_BUG.diff_content)
    findings = [
        Finding(
            id="DG-01",
            title="Valid Finding",
            category=FindingCategory.BUG_OR_LOGIC_ERROR,
            severity=SeverityLevel.HIGH,
            confidence=FindingConfidence.CONFIRMED_ISSUE,
            location=CodeLocation(file_path="payments/processor.py", start_line=46),
            why_identified="Valid added line",
            impact="Crash"
        ),
        Finding(
            id="DG-02",
            title="Invalid File Finding",
            category=FindingCategory.BUG_OR_LOGIC_ERROR,
            severity=SeverityLevel.LOW,
            confidence=FindingConfidence.IMPROVEMENT_SUGGESTION,
            location=CodeLocation(file_path="ghost/missing.ts", start_line=10),
            why_identified="Invalid file",
            impact="None"
        ),
    ]

    results = validate_all_findings(findings, parsed)
    assert len(results) == 2
    assert results[0].location.location_status == LocationStatus.VERIFIED
    assert results[1].location.location_status == LocationStatus.INVALID
