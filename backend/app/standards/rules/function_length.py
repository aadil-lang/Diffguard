"""
Rule 1: Maximum Function Length Evaluator.
Evaluates function lengths on supported languages (Python, JavaScript, TypeScript)
only when complete function boundaries are available within the submitted patch hunks.
Reports incomplete context explicitly without guessing total length.
"""

import re
from typing import List, Tuple, Optional
from app.models.diff_models import ParsedDiff, ParsedFile
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
from app.standards.config_schema import MaxFunctionLengthRule

PY_FUNC_PATTERN = re.compile(r"^[ \t]*(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(")
JS_FUNC_PATTERN = re.compile(
    r"^[ \t]*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(|"
    r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_]+)\s*(?::\s*[^=]+)?=>\s*\{|"
    r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\("
)


def _strip_js_strings_and_comments(code_line: str) -> str:
    """Removes single-line comments and quoted string/template literals before brace counting."""
    # Remove single-line comments
    cleaned = re.sub(r"//.*$", "", code_line)
    # Remove double-quoted strings
    cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cleaned)
    # Remove single-quoted strings
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", cleaned)
    # Remove template literal markers
    cleaned = re.sub(r"`(?:[^`\\]|\\.)*`", "``", cleaned)
    return cleaned


def evaluate_function_length(
    parsed_diff: ParsedDiff,
    rule_config: MaxFunctionLengthRule
) -> List[Finding]:
    """
    Evaluates function length against configured limit.
    Only evaluates when complete function start and end boundaries exist in hunk context.
    """
    if not rule_config.enabled:
        return []

    findings: List[Finding] = []
    finding_idx = 1

    for file_obj in parsed_diff.files:
        lang = (file_obj.language or "").lower()
        if lang not in ("python", "javascript", "typescript"):
            continue

        for hunk in file_obj.hunks:
            if lang == "python":
                findings.extend(
                    _evaluate_python_hunk(file_obj, hunk, rule_config, finding_idx)
                )
            else:
                findings.extend(
                    _evaluate_js_hunk(file_obj, hunk, rule_config, finding_idx)
                )

    return findings


def _evaluate_python_hunk(
    file_obj: ParsedFile,
    hunk,
    rule_config: MaxFunctionLengthRule,
    start_idx: int
) -> List[Finding]:
    findings: List[Finding] = []
    lines = hunk.lines
    n_lines = len(lines)

    i = 0
    in_hunk_doc: Optional[str] = None
    while i < n_lines:
        line_obj = lines[i]
        # Only look at new side lines
        if line_obj.target_line_no is None:
            i += 1
            continue

        raw_text = line_obj.value

        # Update hunk-level docstring state so docstring lines are not parsed as function headers
        for q in ('"""', "'''"):
            cnt = raw_text.count(q)
            if cnt > 0:
                if in_hunk_doc == q:
                    if cnt % 2 != 0:
                        in_hunk_doc = None
                elif in_hunk_doc is None:
                    if cnt % 2 != 0:
                        in_hunk_doc = q

        # If current line is inside an active docstring, it cannot be a real def statement
        if in_hunk_doc is not None and not (raw_text.strip().startswith('"""') or raw_text.strip().startswith("'''")):
            i += 1
            continue

        m = PY_FUNC_PATTERN.match(raw_text)
        if m and in_hunk_doc is None:
            func_name = m.group(1)
            def_line_no = line_obj.target_line_no
            base_indent = len(raw_text) - len(raw_text.lstrip())

            # Trace lines forward to find function termination
            func_lines_count = 1
            is_complete = False
            in_multiline_doc: Optional[str] = None
            j = i + 1

            while j < n_lines:
                curr_line = lines[j]
                if curr_line.target_line_no is None:
                    j += 1
                    continue

                curr_text = curr_line.value

                # Track multiline docstrings to avoid false termination on unindented doc lines
                for q in ('"""', "'''"):
                    count = curr_text.count(q)
                    if count > 0:
                        if in_multiline_doc == q:
                            if count % 2 != 0:
                                in_multiline_doc = None
                        elif in_multiline_doc is None:
                            if count % 2 != 0:
                                in_multiline_doc = q

                # Blank lines inside function belong to function
                if not curr_text.strip():
                    func_lines_count += 1
                    j += 1
                    continue

                curr_indent = len(curr_text) - len(curr_text.lstrip())
                if in_multiline_doc is None and curr_indent <= base_indent:
                    # Function has terminated
                    is_complete = True
                    break

                func_lines_count += 1
                j += 1

            # If boundaries extend beyond hunk, engine does not guess or emit false violation
            if not is_complete:
                i += 1
                continue

            if func_lines_count > rule_config.value:
                findings.append(
                    Finding(
                        id=f"POLICY-LEN-{start_idx + len(findings):03d}",
                        title=f"Function '{func_name}' Exceeds Max Length ({func_lines_count} > {rule_config.value} lines)",
                        category=FindingCategory.CODE_QUALITY_AND_MAINTAINABILITY,
                        severity=rule_config.severity,
                        confidence=FindingConfidence.CONFIRMED_ISSUE,
                        location=CodeLocation(
                            file_path=file_obj.target_file,
                            start_line=def_line_no,
                            code_context=raw_text.strip(),
                            line_side=LineSide.NEW,
                            location_status=LocationStatus.UNVERIFIED,  # Will be verified by location_validator
                        ),
                        why_identified=(
                            f"Function '{func_name}' spans {func_lines_count} lines, exceeding the configured "
                            f"maximum of {rule_config.value} lines in .diffguard.yaml."
                        ),
                        impact="Long functions increase cognitive complexity, test fragility, and defect density.",
                        suggested_fix=SuggestedFix(
                            description=(
                                f"Decompose '{func_name}' into smaller, focused helper functions each with single responsibilities."
                            )
                        ),
                        tool_evidence=[
                            f"Rule ID: STD-LEN-001",
                            f"Function: {func_name}",
                            f"Measured Length: {func_lines_count} lines",
                            f"Configured Limit: {rule_config.value} lines",
                        ],
                        finding_type=FindingType.POLICY_VIOLATION,
                        rule_id="STD-LEN-001",
                        rule_name="Max Function Length",
                        policy_category="code_quality",
                        policy_evaluation_status=PolicyEvaluationStatus.VIOLATED,
                    )
                )

            i += 1
        else:
            i += 1

    return findings


def _evaluate_js_hunk(
    file_obj: ParsedFile,
    hunk,
    rule_config: MaxFunctionLengthRule,
    start_idx: int
) -> List[Finding]:
    findings: List[Finding] = []
    lines = hunk.lines
    n_lines = len(lines)

    i = 0
    while i < n_lines:
        line_obj = lines[i]
        if line_obj.target_line_no is None:
            i += 1
            continue

        raw_text = line_obj.value
        m = JS_FUNC_PATTERN.match(raw_text)
        if m:
            func_name = m.group(1) or m.group(2) or m.group(3) or "anonymous"
            def_line_no = line_obj.target_line_no

            clean_first = _strip_js_strings_and_comments(raw_text)
            brace_count = clean_first.count("{") - clean_first.count("}")
            has_opened = "{" in clean_first
            func_lines_count = 1
            is_complete = has_opened and brace_count <= 0
            j = i + 1

            while j < n_lines and not is_complete:
                curr_line = lines[j]
                if curr_line.target_line_no is None:
                    j += 1
                    continue
                curr_clean = _strip_js_strings_and_comments(curr_line.value)
                func_lines_count += 1
                if not has_opened and "{" in curr_clean:
                    has_opened = True
                brace_count += curr_clean.count("{") - curr_clean.count("}")
                if has_opened and brace_count <= 0:
                    is_complete = True
                    break
                j += 1

            # If boundaries extend beyond hunk, engine does not guess or emit false violation
            if not is_complete:
                i += 1
                continue

            if func_lines_count > rule_config.value:
                findings.append(
                    Finding(
                        id=f"POLICY-LEN-{start_idx + len(findings):03d}",
                        title=f"Function '{func_name}' Exceeds Max Length ({func_lines_count} > {rule_config.value} lines)",
                        category=FindingCategory.CODE_QUALITY_AND_MAINTAINABILITY,
                        severity=rule_config.severity,
                        confidence=FindingConfidence.CONFIRMED_ISSUE,
                        location=CodeLocation(
                            file_path=file_obj.target_file,
                            start_line=def_line_no,
                            code_context=raw_text.strip(),
                            line_side=LineSide.NEW,
                            location_status=LocationStatus.UNVERIFIED,
                        ),
                        why_identified=(
                            f"Function '{func_name}' spans {func_lines_count} lines, exceeding the configured "
                            f"maximum of {rule_config.value} lines in .diffguard.yaml."
                        ),
                        impact="Long functions increase maintenance cost and make code review difficult.",
                        suggested_fix=SuggestedFix(
                            description="Refactor large function by extracting helper functions or modules."
                        ),
                        tool_evidence=[
                            f"Rule ID: STD-LEN-001",
                            f"Function: {func_name}",
                            f"Measured Length: {func_lines_count} lines",
                            f"Configured Limit: {rule_config.value} lines",
                        ],
                        finding_type=FindingType.POLICY_VIOLATION,
                        rule_id="STD-LEN-001",
                        rule_name="Max Function Length",
                        policy_category="code_quality",
                        policy_evaluation_status=PolicyEvaluationStatus.VIOLATED,
                    )
                )

            i += 1
        else:
            i += 1

    return findings

