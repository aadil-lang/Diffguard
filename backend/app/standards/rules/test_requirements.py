"""
Rule 5: Test Change Expectation Evaluator.
Evaluates whether production code changes are accompanied by test modifications
in the submitted patch. Accurately reports missing patch test changes without claiming
tests do not exist in the whole repository.
"""

from typing import List
from app.models.diff_models import ParsedDiff
from app.models.schemas import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingType,
    PolicyEvaluationStatus,
    CodeLocation,
    LocationStatus,
    LineSide,
    SuggestedFix,
)
from app.standards.config_schema import RequireTestChangesRule


CODE_FILE_EXTENSIONS = (
    ".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".java",
    ".rs", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".mjs", ".cjs"
)

TEST_DIR_SEGMENTS = ("/tests/", "/test/", "/__tests__/", "/spec/", "/specs/")
TEST_FILE_SUFFIXES = (
    "_test.py",
    ".test.ts", ".test.js", ".test.jsx", ".test.tsx", ".test.mjs", ".test.cjs",
    ".spec.ts", ".spec.js", ".spec.jsx", ".spec.tsx", ".spec.mjs", ".spec.cjs"
)


def is_test_file(path: str) -> bool:
    """Accurately identifies test files using path directory segments and file name conventions."""
    norm = "/" + path.lower().replace("\\", "/").lstrip("/")
    filename = norm.split("/")[-1]

    # Check directory segment conventions
    if any(td in norm for td in TEST_DIR_SEGMENTS):
        return True

    # Check Python test_*.py prefix
    if filename.startswith("test_") and filename.endswith(".py"):
        return True

    # Check explicit test suffixes
    if any(filename.endswith(sfx) for sfx in TEST_FILE_SUFFIXES):
        return True

    return False


def is_production_code_file(path: str) -> bool:
    """Identifies actual business logic code files, ignoring documentation, config, and images."""
    if is_test_file(path):
        return False
    norm = path.lower().replace("\\", "/")
    filename = norm.split("/")[-1]
    return any(filename.endswith(ext) for ext in CODE_FILE_EXTENSIONS)


def evaluate_require_test_changes(
    parsed_diff: ParsedDiff,
    rule_config: RequireTestChangesRule
) -> List[Finding]:
    """
    Checks if production code modifications meet the additions threshold without
    accompanying test changes in the submitted patch.
    """
    if not rule_config.enabled:
        return []

    test_files = [f for f in parsed_diff.files if is_test_file(f.target_file)]
    prod_files = [f for f in parsed_diff.files if is_production_code_file(f.target_file)]

    # If test files are present in the patch, the patch requirement is satisfied
    if test_files:
        return []

    findings: List[Finding] = []
    finding_idx = 1

    for f in prod_files:
        if f.additions >= rule_config.min_additions_threshold:
            findings.append(
                Finding(
                    id=f"POLICY-TEST-{finding_idx:03d}",
                    title="No Corresponding Test Changes in Submitted Patch",
                    category=FindingCategory.MISSING_TEST_COVERAGE,
                    severity=rule_config.severity,
                    confidence=FindingConfidence.POTENTIAL_ISSUE,
                    location=CodeLocation(
                        file_path=f.target_file,
                        start_line=1,
                        line_side=LineSide.FILE_LEVEL,
                        location_status=LocationStatus.FILE_LEVEL,
                        validation_note="Finding applies to the file as a whole rather than a specific line.",
                    ),
                    why_identified=(
                        f"Production file '{f.target_file}' includes {f.additions} added lines, but No "
                        f"corresponding test changes were detected in the submitted patch (configured threshold: "
                        f"{rule_config.min_additions_threshold} additions)."
                    ),
                    impact=(
                        "Modifying business logic without accompanying test assertions increases regression risk. "
                        "Note: Existing tests may exist outside this patch, but none were updated alongside these changes."
                    ),
                    suggested_fix=SuggestedFix(
                        description=(
                            "Include unit or integration test assertions in this patch covering the newly introduced code paths."
                        )
                    ),
                    tool_evidence=[
                        f"Rule ID: STD-TEST-001",
                        f"Production File: {f.target_file}",
                        f"Added Lines: {f.additions}",
                        f"Threshold: {rule_config.min_additions_threshold}",
                        "Patch Test Files: 0 detected",
                    ],
                    finding_type=FindingType.POLICY_VIOLATION,
                    rule_id="STD-TEST-001",
                    rule_name="Require Test Changes",
                    policy_category="testing",
                    policy_evaluation_status=PolicyEvaluationStatus.VIOLATED,
                )
            )
            finding_idx += 1

    return findings
