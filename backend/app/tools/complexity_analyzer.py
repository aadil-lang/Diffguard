"""
Complexity and Metrics Analyzer Tool: Evaluates cyclomatic complexity,
cognitive nesting depth, and code churn to highlight maintainability hazards.
"""

import re
from typing import Dict, Any


BRANCH_PATTERN = re.compile(
    r"\b(if|elif|else\s+if|for|while|case|catch|except)\b|(\&\&|\|\||\?)"
)


def analyze_complexity(code_snippet: str, file_path: str = "") -> Dict[str, Any]:
    """
    Computes cyclomatic complexity, nesting depth, and code churn on the changed lines.
    """
    lines = code_snippet.splitlines()
    added_lines = [l for l in lines if l.startswith("+") and not l.startswith("+++")]
    deleted_lines = [l for l in lines if l.startswith("-") and not l.startswith("---")]

    additions_count = len(added_lines)
    deletions_count = len(deleted_lines)

    # Calculate cyclomatic complexity on added code
    complexity_score = 1
    max_nesting_depth = 0

    for line in added_lines:
        content = line[1:].rstrip()
        if not content.strip():
            continue
        
        # Calculate leading whitespace indentation for nesting
        leading_spaces = len(content) - len(content.lstrip())
        indent_level = leading_spaces // 4  # Standard 4 spaces
        if indent_level > max_nesting_depth:
            max_nesting_depth = indent_level

        # Branch points
        matches = BRANCH_PATTERN.findall(content)
        complexity_score += len(matches)

    # Maintainability risk assessment
    risk_level = "LOW"
    warning = None

    if complexity_score > 14 or max_nesting_depth >= 6:
        risk_level = "HIGH"
        warning = f"High cyclomatic complexity ({complexity_score}) and deep nesting (depth {max_nesting_depth}). Consider extracting helper functions to reduce cognitive load and testing difficulty."
    elif complexity_score > 9 or max_nesting_depth >= 5:
        risk_level = "MEDIUM"
        warning = f"Moderate complexity ({complexity_score}). Ensure all branch paths have dedicated unit test cases."

    return {
        "file_path": file_path,
        "cyclomatic_complexity": complexity_score,
        "max_nesting_depth": max_nesting_depth,
        "additions_count": additions_count,
        "deletions_count": deletions_count,
        "risk_level": risk_level,
        "warning": warning
    }

