"""
Test Requirement Analyzer Tool: Evaluates whether code modifications require corresponding unit or integration tests.
"""

from typing import List, Dict, Any
from app.models.diff_models import ParsedDiff


def analyze_test_coverage(parsed_diff: ParsedDiff) -> List[Dict[str, Any]]:
    """
    Evaluates whether business logic changes are accompanied by test updates.
    """
    test_files = []
    prod_files = []

    for f in parsed_diff.files:
        path_lower = f.target_file.lower()
        if (
            "test" in path_lower
            or "spec" in path_lower
            or path_lower.endswith("_test.py")
            or path_lower.startswith("tests/")
        ):
            test_files.append(f)
        else:
            prod_files.append(f)

    findings = []

    # If there are production modifications but zero test modifications:
    if prod_files and not test_files:
        for f in prod_files:
            # Significant addition check or core module check
            if f.additions >= 8:
                findings.append({
                    "tool": "test_requirement_analyzer",
                    "file_path": f.target_file,
                    "severity": "HIGH" if f.additions > 25 else "MEDIUM",
                    "message": (
                        f"Production file '{f.target_file}' had {f.additions} added lines without any corresponding unit or integration test changes in this patch."
                    ),
                    "suggested_tests": [
                        "Unit test verifying standard successful execution (happy path)",
                        "Boundary and edge case test for null/empty/invalid inputs",
                        "Error handling / exception propagation test"
                    ]
                })

    return findings

