"""
Rule 3: Prohibited Imports Evaluator.
Detects import statements for forbidden modules/packages in newly added lines.
Supports Python and JavaScript/TypeScript import syntax.
"""

import re
from typing import List, Set
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
from app.standards.config_schema import ProhibitedImportsRule

PY_IMPORT_RE = re.compile(
    r"^[ \t]*(?:import\s+([A-Za-z0-9_\.]+)|from\s+([A-Za-z0-9_\.]+)\s+import)"
)
JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))"""
)


def evaluate_prohibited_imports(
    parsed_diff: ParsedDiff,
    rule_config: ProhibitedImportsRule
) -> List[Finding]:
    """
    Scans newly added lines for imports matching the configured prohibited list.
    """
    if not rule_config.enabled or not rule_config.values:
        return []

    prohibited_set: Set[str] = {v.lower().strip() for v in rule_config.values if v.strip()}
    findings: List[Finding] = []
    finding_idx = 1

    for file_obj in parsed_diff.files:
        lang = (file_obj.language or "").lower()

        for hunk in file_obj.hunks:
            for line in hunk.lines:
                if line.line_type != "+" or line.target_line_no is None:
                    continue

                content = line.value.strip()
                matched_pkg = None

                if lang == "python" or file_obj.target_file.endswith(".py"):
                    clean_py = content.split("#")[0].strip()
                    # Pattern 1: import a, b as c, d
                    m_imp = re.match(r"^[ \t]*import\s+(.+)$", clean_py)
                    if m_imp:
                        raw_mods = m_imp.group(1).split(",")
                        for rm in raw_mods:
                            token = rm.strip()
                            if not token:
                                continue
                            mod_name = token.split()[0].split(".")[0].lower()
                            if mod_name in prohibited_set:
                                matched_pkg = mod_name
                                break

                    # Pattern 2: from a.b import c, d as e
                    if not matched_pkg:
                        m_from = re.match(r"^[ \t]*from\s+([A-Za-z0-9_\.]+)\s+import\s+(.+)$", clean_py)
                        if m_from:
                            base_pkg = m_from.group(1).split(".")[0].lower()
                            if base_pkg in prohibited_set:
                                matched_pkg = base_pkg
                            else:
                                raw_syms = m_from.group(2).split(",")
                                for rs in raw_syms:
                                    sym_token = rs.strip()
                                    if not sym_token:
                                        continue
                                    sym_name = sym_token.split()[0].lower()
                                    if sym_name in prohibited_set:
                                        matched_pkg = sym_name
                                        break

                elif lang in ("javascript", "typescript") or any(
                    file_obj.target_file.endswith(ext) for ext in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")
                ):
                    clean_js = content.split("//")[0].strip()
                    m_js = re.search(
                        r"""(?:import\s+(?:.*?from\s+)?['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
                        clean_js
                    )
                    if m_js:
                        raw_pkg = (m_js.group(1) or m_js.group(2) or "").strip().lower()
                        if raw_pkg in prohibited_set:
                            matched_pkg = raw_pkg
                        else:
                            # Support scoped packages (@scope/pkg) and standard subpackages (pkg/sub)
                            base_pkg = "/".join(raw_pkg.split("/")[:2]) if raw_pkg.startswith("@") else raw_pkg.split("/")[0]
                            if base_pkg in prohibited_set:
                                matched_pkg = base_pkg
                else:
                    # General keyword match on non-comment import lines
                    clean_gen = re.sub(r"#.*|//.*|/\*.*?\*/", "", content).strip()
                    for candidate in prohibited_set:
                        if re.search(rf"\b(import|require|using|include)\b[^\n;]*\b{re.escape(candidate)}\b", clean_gen):
                            matched_pkg = candidate
                            break

                if matched_pkg:
                    findings.append(
                        Finding(
                            id=f"POLICY-IMP-{finding_idx:03d}",
                            title=f"Prohibited Import '{matched_pkg}' Detected",
                            category=FindingCategory.SECURITY_AND_RELIABILITY,
                            severity=rule_config.severity,
                            confidence=FindingConfidence.CONFIRMED_ISSUE,
                            location=CodeLocation(
                                file_path=file_obj.target_file,
                                start_line=line.target_line_no,
                                code_context=content,
                                line_side=LineSide.NEW,
                                location_status=LocationStatus.UNVERIFIED,
                            ),
                            why_identified=(
                                f"Import statement imports prohibited module '{matched_pkg}', violating the "
                                f"prohibited_imports security policy in .diffguard.yaml."
                            ),
                            impact=(
                                f"Use of prohibited module '{matched_pkg}' violates repository architecture or security compliance "
                                f"(e.g., insecure deserialization, deprecated protocols, unvetted dependencies)."
                            ),
                            suggested_fix=SuggestedFix(
                                description=f"Remove import of '{matched_pkg}' and use an approved alternative (e.g. json, safe_load, cryptography)."
                            ),
                            tool_evidence=[
                                f"Rule ID: STD-IMP-001",
                                f"Prohibited Module: {matched_pkg}",
                                f"Statement: {content}",
                            ],
                            finding_type=FindingType.POLICY_VIOLATION,
                            rule_id="STD-IMP-001",
                            rule_name="Prohibited Imports",
                            policy_category="security",
                            policy_evaluation_status=PolicyEvaluationStatus.VIOLATED,
                        )
                    )
                    finding_idx += 1

    return findings

