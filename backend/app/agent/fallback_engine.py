"""
Deterministic Fallback Engine: Provides full, structured code review capability
in offline environments, when Gemini API key is unconfigured, or during upstream outages.
"""

import re
from typing import List, Dict, Any
from app.models.schemas import (
    Finding,
    FindingCategory,
    SeverityLevel,
    FindingConfidence,
    CodeLocation,
    SuggestedFix,
    ReviewSummary,
    ReviewResponse,
    ProcessingStage,
    StageStatus
)
from app.models.diff_models import ParsedDiff


def run_heuristic_code_review(
    parsed_diff: ParsedDiff,
    tool_results: Dict[str, Any],
    stages: List[ProcessingStage]
) -> ReviewResponse:
    """
    Synthesize structured findings from empirical tool evidence and heuristic static analysis.
    """
    findings: List[Finding] = []
    finding_counter = 1

    # 1. Process Security Findings
    for sec in tool_results.get("security_findings", []):
        sev_str = sec.get("severity", "HIGH")
        sev = SeverityLevel[sev_str] if sev_str in SeverityLevel.__members__ else SeverityLevel.HIGH
        
        f_id = f"DG-{finding_counter:03d}"
        finding_counter += 1

        findings.append(
            Finding(
                id=f_id,
                title=f"{sec.get('name', 'Security Flaw')} ({sec.get('cwe', 'CWE')})",
                category=FindingCategory.SECURITY_AND_RELIABILITY,
                severity=sev,
                confidence=FindingConfidence.CONFIRMED_ISSUE,
                location=CodeLocation(
                    file_path=sec.get("file_path", "unknown"),
                    start_line=sec.get("adjusted_line", sec.get("line_number", 1)),
                    code_context=sec.get("matched_code", "")
                ),
                why_identified=sec.get("description", "Vulnerability detected by static security pattern analyzer."),
                impact="Could expose sensitive data, allow injection attacks, or compromise system integrity.",
                suggested_fix=SuggestedFix(
                    description=sec.get("remediation", "Remediate by using secure APIs or parameterized calls."),
                    replacement_code=sec.get("remediation")
                ),
                tool_evidence=[f"Rule ID: {sec.get('rule_id')}", f"CWE: {sec.get('cwe')}"]
            )
        )

    # 2. Process Syntax & Linter Findings
    for syn in tool_results.get("syntax_findings", []):
        f_id = f"DG-{finding_counter:03d}"
        finding_counter += 1
        
        sev_str = syn.get("severity", "MEDIUM")
        sev = SeverityLevel[sev_str] if sev_str in SeverityLevel.__members__ else SeverityLevel.MEDIUM

        category = FindingCategory.BUG_OR_LOGIC_ERROR
        if syn.get("type") == "LOOSE_EQUALITY":
            category = FindingCategory.STYLE_AND_CONSISTENCY

        findings.append(
            Finding(
                id=f_id,
                title=f"{syn.get('type', 'Syntax Warning').replace('_', ' ').title()}",
                category=category,
                severity=sev,
                confidence=FindingConfidence.CONFIRMED_ISSUE if syn.get("type") == "SYNTAX_ERROR" else FindingConfidence.POTENTIAL_ISSUE,
                location=CodeLocation(
                    file_path=syn.get("file_path", "unknown"),
                    start_line=syn.get("adjusted_line", syn.get("line_number", 1)),
                    code_context=syn.get("text", "")
                ),
                why_identified=syn.get("message", "Syntax or linter violation identified in added code."),
                impact="May lead to runtime exceptions, race conditions, or unhandled errors in production.",
                suggested_fix=SuggestedFix(
                    description="Update the code to handle asynchronous promises or avoid bare exception catching."
                ),
                tool_evidence=[f"Tool: {syn.get('tool')}", f"Type: {syn.get('type')}"]
            )
        )

    # 3. Process Code Complexity Findings
    for comp in tool_results.get("complexity_findings", []):
        f_id = f"DG-{finding_counter:03d}"
        finding_counter += 1

        sev = SeverityLevel.HIGH if comp.get("risk_level") == "HIGH" else SeverityLevel.MEDIUM

        findings.append(
            Finding(
                id=f_id,
                title="Excessive Cyclomatic Complexity & Deep Nesting",
                category=FindingCategory.CODE_QUALITY_AND_MAINTAINABILITY,
                severity=sev,
                confidence=FindingConfidence.IMPROVEMENT_SUGGESTION,
                location=CodeLocation(
                    file_path=comp.get("file_path", "unknown"),
                    start_line=1
                ),
                why_identified=comp.get("warning", "Cyclomatic complexity exceeds maintainability thresholds."),
                impact="High cognitive load makes this code prone to regression bugs and difficult to test comprehensively.",
                suggested_fix=SuggestedFix(
                    description="Decompose complex nested conditionals into smaller, dedicated helper methods or early-return guards."
                ),
                tool_evidence=[
                    f"Cyclomatic Complexity: {comp.get('cyclomatic_complexity')}",
                    f"Max Nesting Depth: {comp.get('max_nesting_depth')}"
                ]
            )
        )

    # 4. Process Test Coverage Findings
    for test_issue in tool_results.get("test_coverage_findings", []):
        f_id = f"DG-{finding_counter:03d}"
        finding_counter += 1

        sev_str = test_issue.get("severity", "MEDIUM")
        sev = SeverityLevel[sev_str] if sev_str in SeverityLevel.__members__ else SeverityLevel.MEDIUM

        tests_formatted = "\n- " + "\n- ".join(test_issue.get("suggested_tests", []))

        findings.append(
            Finding(
                id=f_id,
                title="Untested Production Code Modifications",
                category=FindingCategory.MISSING_TEST_COVERAGE,
                severity=sev,
                confidence=FindingConfidence.POTENTIAL_ISSUE,
                location=CodeLocation(
                    file_path=test_issue.get("file_path", "unknown"),
                    start_line=1
                ),
                why_identified=test_issue.get("message", "Production logic modified without corresponding tests."),
                impact="Changes to core logic without unit/integration tests increase the risk of silent production regressions.",
                suggested_fix=SuggestedFix(
                    description=f"Add unit test assertions covering:{tests_formatted}"
                ),
                tool_evidence=["Diff has production modifications with zero accompanying test files."]
            )
        )

    # 5. Heuristic checks on hunks for Resource Leaks and Off-by-one errors
    for file_obj in parsed_diff.files:
        for hunk in file_obj.hunks:
            for idx, line in enumerate(hunk.added_lines, start=1):
                # Resource leak: open() without with
                if re.search(r"=\s*open\s*\(", line) and "with" not in line:
                    f_id = f"DG-{finding_counter:03d}"
                    finding_counter += 1
                    findings.append(
                        Finding(
                            id=f_id,
                            title="Unclosed File Resource Leak",
                            category=FindingCategory.SECURITY_AND_RELIABILITY,
                            severity=SeverityLevel.HIGH,
                            confidence=FindingConfidence.CONFIRMED_ISSUE,
                            location=CodeLocation(
                                file_path=file_obj.target_file,
                                start_line=hunk.target_start + idx - 1,
                                code_context=line
                            ),
                            why_identified="Opening file descriptor without a context manager ('with open(...)') risks resource exhaustion if an exception occurs.",
                            impact="File descriptor leaks under high load can cause 'Too many open files' OS crashes.",
                            suggested_fix=SuggestedFix(
                                description="Refactor to use standard context manager: 'with open(...) as f:'",
                                replacement_code=f"with {line.strip()}:"
                            ),
                            tool_evidence=["Detected naked open() assignment in added lines."]
                        )
                    )

                # Off-by-one check in loop bounds: range(len(...) + 1)
                if re.search(r"range\s*\(\s*len\s*\([^)]+\)\s*\+\s*1\s*\)", line):
                    f_id = f"DG-{finding_counter:03d}"
                    finding_counter += 1
                    findings.append(
                        Finding(
                            id=f_id,
                            title="Off-by-One Array Indexing Out-of-Bounds Error",
                            category=FindingCategory.BUG_OR_LOGIC_ERROR,
                            severity=SeverityLevel.CRITICAL,
                            confidence=FindingConfidence.CONFIRMED_ISSUE,
                            location=CodeLocation(
                                file_path=file_obj.target_file,
                                start_line=hunk.target_start + idx - 1,
                                code_context=line
                            ),
                            why_identified="Loop boundary 'range(len(items) + 1)' causes IndexError when indexing items[i] at the final iteration.",
                            impact="Immediate runtime crash (IndexError) when loop encounters end of array.",
                            suggested_fix=SuggestedFix(
                                description="Change range to standard 'range(len(items))' or iterate directly over items: 'for item in items:'",
                                replacement_code=line.replace("+ 1", "").replace("+1", "")
                            ),
                            tool_evidence=["Detected range(len(...) + 1) pattern in loop header."]
                        )
                    )

    # Build Summary
    by_sev: Dict[str, int] = {s.value: 0 for s in SeverityLevel}
    by_cat: Dict[str, int] = {c.value: 0 for c in FindingCategory}
    by_conf: Dict[str, int] = {cf.value: 0 for cf in FindingConfidence}

    for f in findings:
        by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
        by_cat[f.category.value] = by_cat.get(f.category.value, 0) + 1
        by_conf[f.confidence.value] = by_conf.get(f.confidence.value, 0) + 1

    # Determine overall verdict
    if by_sev.get("CRITICAL", 0) > 0:
        verdict = "CRITICAL_BLOCKER"
    elif by_sev.get("HIGH", 0) > 0:
        verdict = "CHANGES_REQUESTED"
    elif len(findings) > 0:
        verdict = "APPROVED_WITH_COMMENTS"
    else:
        verdict = "APPROVED"

    key_takeaways = []
    if by_sev.get("CRITICAL", 0) > 0:
        key_takeaways.append(f"Blocked by {by_sev['CRITICAL']} Critical issue(s) that must be remediated immediately.")
    if by_sev.get("HIGH", 0) > 0:
        key_takeaways.append(f"Identified {by_sev['HIGH']} High severity risk(s) requiring revision.")
    if by_cat.get("MISSING_TEST_COVERAGE", 0) > 0:
        key_takeaways.append("Test coverage is missing for newly added business logic paths.")
    if not findings:
        key_takeaways.append("Clean patch: No high or critical issues detected. Well structured.")

    summary = ReviewSummary(
        total_findings=len(findings),
        by_severity=by_sev,
        by_category=by_cat,
        by_confidence=by_conf,
        verdict=verdict,
        key_takeaways=key_takeaways
    )

    import datetime
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return ReviewResponse(
        review_id=f"rev_{int(datetime.datetime.now().timestamp())}",
        timestamp=now_str,
        parsed_files_count=parsed_diff.total_files,
        total_additions=parsed_diff.total_additions,
        total_deletions=parsed_diff.total_deletions,
        summary=summary,
        findings=findings,
        stages_executed=stages,
        engine_used="deterministic-heuristic-engine"
    )

