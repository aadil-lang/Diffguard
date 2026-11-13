"""
Tests for Agent Schema, Output Validation, and Fallback Engine.
"""

from app.models.schemas import (
    ReviewRequest,
    ReviewResponse,
    Finding,
    FindingCategory,
    SeverityLevel,
    FindingConfidence,
    CodeLocation,
    ProcessingStage,
    StageStatus
)
from app.parser.diff_parser import parse_git_diff
from app.tools.tool_registry import execute_all_analysis_tools
from app.agent.fallback_engine import run_heuristic_code_review
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH, SAMPLE_CLEAN_PR


def test_finding_model_validation():
    finding = Finding(
        id="DG-001",
        title="SQL Injection",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.CRITICAL,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="auth.py", start_line=15),
        why_identified="Formatted string used in cursor.execute",
        impact="Critical data leakage or database compromise."
    )
    assert finding.id == "DG-001"
    assert finding.severity == SeverityLevel.CRITICAL


def test_heuristic_fallback_engine_on_sqli():
    parsed = parse_git_diff(SAMPLE_SQLI_AUTH.diff_content)
    tools = execute_all_analysis_tools(parsed)
    stages = [ProcessingStage(stage_id="STAGE_RECEIVED", name="Received", status=StageStatus.COMPLETED)]

    response = run_heuristic_code_review(parsed, tools, stages)
    assert isinstance(response, ReviewResponse)
    assert len(response.findings) >= 2  # SQLi and JWT secret
    assert response.summary.by_severity.get("CRITICAL", 0) >= 1
    assert response.summary.verdict in ("CRITICAL_BLOCKER", "CHANGES_REQUESTED")


def test_heuristic_fallback_engine_on_clean_pr():
    parsed = parse_git_diff(SAMPLE_CLEAN_PR.diff_content)
    tools = execute_all_analysis_tools(parsed)
    stages = [ProcessingStage(stage_id="STAGE_RECEIVED", name="Received", status=StageStatus.COMPLETED)]

    response = run_heuristic_code_review(parsed, tools, stages)
    assert isinstance(response, ReviewResponse)
    assert response.summary.by_severity.get("CRITICAL", 0) == 0
    assert response.summary.by_severity.get("HIGH", 0) == 0
    assert response.summary.verdict in ("APPROVED", "APPROVED_WITH_COMMENTS")

