"""
Rule 2: Maximum Nesting Depth Evaluator.
Evaluates nesting depth on newly added code lines against the configured limit.
Avoids naive brace counting by analyzing block indentation and branch control constructs.
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
from app.standards.config_schema import MaxNestingDepthRule


def evaluate_nesting_depth(
    parsed_diff: ParsedDiff,
    rule_config: MaxNestingDepthRule
) -> List[Finding]:
    """
    Evaluates indentation-based nesting depth on added lines.
    Flags locations where indentation level exceeds configured limit.
    """
    if not rule_config.enabled:
        return []

    findings: List[Finding] = []
    finding_idx = 1

    for file_obj in parsed_diff.files:
        lang = (file_obj.language or "").lower()
        # Supported programming languages (exclude data/config formats like json, yaml, markdown)
        if lang not in ("python", "javascript", "typescript", "go", "java", "c", "cpp", "csharp", "rust", "ruby", "php"):
            continue

        for hunk in file_obj.hunks:
            max_depth_in_hunk = 0
            deepest_line_no = None
            deepest_text = None

            # Detect indentation step (2 vs 4 spaces) across hunk
            indent_values = []
            for line in hunk.lines:
                if line.target_line_no is not None:
                    exp = line.value.expandtabs(4)
                    sp = len(exp) - len(exp.lstrip(" "))
                    if sp > 0:
                        indent_values.append(sp)

            indent_step = 4
            if any(v % 4 != 0 and v % 2 == 0 for v in indent_values):
                indent_step = 2

            paren_depth = 0
            for line in hunk.lines:
                # Only inspect newly added lines
                if line.line_type != "+" or line.target_line_no is None:
                    # Update paren depth on context lines too
                    clean_ctx = line.value.expandtabs(4).split("#")[0].split("//")[0]
                    paren_depth += clean_ctx.count("(") - clean_ctx.count(")")
                    paren_depth = max(0, paren_depth)
                    continue

                content = line.value.expandtabs(4)
                stripped = content.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*"):
                    continue

                clean_line = stripped.split("#")[0].split("//")[0]
                is_arg_alignment = paren_depth > 0 and not any(
                    clean_line.startswith(kw) for kw in ("if ", "for ", "while ", "def ", "function ", "class ", "try", "switch")
                ) and "{" not in clean_line

                paren_depth += clean_line.count("(") - clean_line.count(")")
                paren_depth = max(0, paren_depth)

                if is_arg_alignment:
                    continue

                leading_spaces = len(content) - len(content.lstrip(" "))
                indent_level = leading_spaces // indent_step

                if indent_level > max_depth_in_hunk:
                    max_depth_in_hunk = indent_level
                    deepest_line_no = line.target_line_no
                    deepest_text = stripped

            if max_depth_in_hunk > rule_config.value and deepest_line_no is not None:
                findings.append(
                    Finding(
                        id=f"POLICY-NEST-{finding_idx:03d}",
                        title=f"Nesting Depth Exceeds Standard (Depth {max_depth_in_hunk} > {rule_config.value})",
                        category=FindingCategory.CODE_QUALITY_AND_MAINTAINABILITY,
                        severity=rule_config.severity,
                        confidence=FindingConfidence.CONFIRMED_ISSUE,
                        location=CodeLocation(
                            file_path=file_obj.target_file,
                            start_line=deepest_line_no,
                            code_context=deepest_text,
                            line_side=LineSide.NEW,
                            location_status=LocationStatus.UNVERIFIED,
                        ),
                        why_identified=(
                            f"Code line at depth {max_depth_in_hunk} exceeds maximum configured nesting depth of "
                            f"{rule_config.value} in .diffguard.yaml."
                        ),
                        impact="Deeply nested conditionals and loops sharply increase cognitive load and defect probability.",
                        suggested_fix=SuggestedFix(
                            description=(
                                "Refactor using early return guards, extract inner loop/conditional logic into "
                                "dedicated helper functions, or replace nested conditionals with lookup structures."
                            )
                        ),
                        tool_evidence=[
                            f"Rule ID: STD-NEST-001",
                            f"Max Observed Nesting: {max_depth_in_hunk}",
                            f"Configured Limit: {rule_config.value}",
                        ],
                        finding_type=FindingType.POLICY_VIOLATION,
                        rule_id="STD-NEST-001",
                        rule_name="Max Nesting Depth",
                        policy_category="code_quality",
                        policy_evaluation_status=PolicyEvaluationStatus.VIOLATED,
                    )
                )
                finding_idx += 1

    return findings

