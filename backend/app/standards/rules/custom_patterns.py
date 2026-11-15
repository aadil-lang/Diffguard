"""
Rule 4: Custom Pattern Rules Evaluator.
Executes pre-compiled regular expressions against added code lines.
Safe execution: no eval/exec, bounded patterns, duplicate suppression.
"""

import re
import re2
from typing import List, Set, Tuple
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
from app.tools.security_scanner import redact_sensitive_line
from app.standards.config_schema import CustomPatternsRule


def evaluate_custom_patterns(
    parsed_diff: ParsedDiff,
    rule_config: CustomPatternsRule
) -> List[Finding]:
    """
    Evaluates configured custom pattern rules against added lines in the patch.
    """
    if not rule_config.enabled or not rule_config.rules:
        return []

    findings: List[Finding] = []
    seen_locations: Set[Tuple[str, str, int]] = set()

    # Pre-compile active patterns with RE2 for guaranteed linear-time matching
    compiled_rules = []
    for r in rule_config.rules:
        try:
            compiled = re2.compile(r.pattern)
            compiled_rules.append((r, compiled))
        except Exception:
            continue

    finding_idx = 1
    for file_obj in parsed_diff.files:
        for hunk in file_obj.hunks:
            for line in hunk.lines:
                if line.line_type != "+" or line.target_line_no is None:
                    continue

                content = line.value
                line_no = line.target_line_no

                for rule_item, compiled_re in compiled_rules:
                    key = (rule_item.id, file_obj.target_file, line_no)
                    if key in seen_locations:
                        continue

                    if compiled_re.search(content):
                        seen_locations.add(key)
                        findings.append(
                            Finding(
                                id=f"POLICY-PAT-{finding_idx:03d}",
                                title=f"Policy Violation: {rule_item.name}",
                                category=FindingCategory.SECURITY_AND_RELIABILITY,
                                severity=rule_item.severity,
                                confidence=FindingConfidence.CONFIRMED_ISSUE,
                                location=CodeLocation(
                                    file_path=file_obj.target_file,
                                    start_line=line_no,
                                    code_context=redact_sensitive_line(content.strip()),
                                    line_side=LineSide.NEW,
                                    location_status=LocationStatus.UNVERIFIED,
                                ),
                                why_identified=(
                                    rule_item.description or
                                    f"Line matches custom repository policy rule '{rule_item.name}' (ID: {rule_item.id}) pattern '{rule_item.pattern}'."
                                ),
                                impact="Code violates explicit team standard configured in .diffguard.yaml.",
                                suggested_fix=SuggestedFix(
                                    description=f"Refactor to comply with policy standard '{rule_item.name}'."
                                ),
                                tool_evidence=[
                                    f"Rule ID: {rule_item.id}",
                                    f"Rule Name: {rule_item.name}",
                                    f"Pattern: {rule_item.pattern}",
                                    f"Matched Code: {redact_sensitive_line(content.strip())}",
                                ],
                                finding_type=FindingType.POLICY_VIOLATION,
                                rule_id=rule_item.id,
                                rule_name=rule_item.name,
                                policy_category="custom_patterns",
                                policy_evaluation_status=PolicyEvaluationStatus.VIOLATED,
                            )
                        )
                        finding_idx += 1

    return findings

