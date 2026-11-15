"""
Engineering Standards Rule Engine: Deterministically evaluates all configured
repository policies against the submitted unified diff.
"""

from typing import List, Dict, Any, Set, Tuple
from app.models.diff_models import ParsedDiff
from app.models.schemas import Finding, FindingType, PolicyEvaluationStatus
from app.standards.config_schema import DiffguardConfig
from app.standards.rules.function_length import evaluate_function_length
from app.standards.rules.nesting_depth import evaluate_nesting_depth
from app.standards.rules.prohibited_imports import evaluate_prohibited_imports
from app.standards.rules.custom_patterns import evaluate_custom_patterns
from app.standards.rules.test_requirements import evaluate_require_test_changes


class EngineeringStandardsEngine:
    """
    Orchestrates deterministic evaluation of repository-specific engineering standards.
    Operates strictly in-memory against parsed diff structures without executing code or shell commands.
    """

    def __init__(self, config: DiffguardConfig):
        self.config = config

    def evaluate(self, parsed_diff: ParsedDiff) -> List[Finding]:
        """
        Runs all active policy rules against the parsed diff and returns deduplicated policy findings.
        """
        findings: List[Finding] = []
        standards = self.config.standards

        # Rule 1: Max Function Length
        if standards.code_quality and standards.code_quality.max_function_length:
            findings.extend(
                evaluate_function_length(parsed_diff, standards.code_quality.max_function_length)
            )

        # Rule 2: Max Nesting Depth
        if standards.code_quality and standards.code_quality.max_nesting_depth:
            findings.extend(
                evaluate_nesting_depth(parsed_diff, standards.code_quality.max_nesting_depth)
            )

        # Rule 3: Prohibited Imports
        if standards.security and standards.security.prohibited_imports:
            findings.extend(
                evaluate_prohibited_imports(parsed_diff, standards.security.prohibited_imports)
            )

        # Rule 4: Custom Patterns
        if standards.security and standards.security.custom_patterns:
            findings.extend(
                evaluate_custom_patterns(parsed_diff, standards.security.custom_patterns)
            )

        # Rule 5: Require Test Changes
        if standards.testing and standards.testing.require_test_changes:
            findings.extend(
                evaluate_require_test_changes(parsed_diff, standards.testing.require_test_changes)
            )

        # Deterministic deduplication by (rule_id, file_path, start_line)
        seen: Set[Tuple[str, str, int]] = set()
        deduped: List[Finding] = []

        for f in findings:
            key = (f.rule_id or f.title, f.location.file_path, f.location.start_line)
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        return deduped

    def get_rules_status(self) -> Dict[str, Any]:
        """
        Returns status summary of configured rules for prompt context or telemetry.
        """
        standards = self.config.standards
        active_rules = []

        if standards.code_quality:
            if standards.code_quality.max_function_length and standards.code_quality.max_function_length.enabled:
                active_rules.append(f"max_function_length (limit: {standards.code_quality.max_function_length.value} lines)")
            if standards.code_quality.max_nesting_depth and standards.code_quality.max_nesting_depth.enabled:
                active_rules.append(f"max_nesting_depth (limit: {standards.code_quality.max_nesting_depth.value})")

        if standards.security:
            if standards.security.prohibited_imports and standards.security.prohibited_imports.enabled:
                active_rules.append(f"prohibited_imports ({len(standards.security.prohibited_imports.values)} packages)")
            if standards.security.custom_patterns and standards.security.custom_patterns.enabled:
                active_rules.append(f"custom_patterns ({len(standards.security.custom_patterns.rules)} patterns)")

        if standards.testing:
            if standards.testing.require_test_changes and standards.testing.require_test_changes.enabled:
                active_rules.append(f"require_test_changes (threshold: {standards.testing.require_test_changes.min_additions_threshold} lines)")

        return {
            "project_name": self.config.project.name if self.config.project else "default",
            "active_rules_count": len(active_rules),
            "active_rules": active_rules,
        }

