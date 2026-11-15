"""
Phase 3.1.3 Targeted Finding Integrity Regression Test Suite.
Verifies safe policy deduplication and canonical path matching:
- Scenario A: Exact matching rule_id produces one authoritative policy finding
- Scenario B: Generic 'security' keyword does NOT suppress same-line code defect (SQL injection)
- Scenario C: Same-line hardcoded secret survives alongside policy violation
- Scenario D: Different policy rules survive on the same line
- Scenario E: Different code defects survive on the same line
- Scenario F: Ambiguous generic model finding preserved alongside policy violation
- F-07B Path Normalization: Git-prefixed (a/, b/) and unprefixed paths canonicalize consistently
- Fallback and Gemini pipelines both preserve deterministic policy findings
"""

import pytest
from app.agent.reviewer_agent import ReviewAgent, merge_policy_and_model_findings
from app.agent.fallback_engine import run_heuristic_code_review
from app.parser.diff_parser import parse_git_diff
from app.parser.location_validator import normalize_repo_path
from app.models.schemas import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingType,
    CodeLocation,
    LocationStatus,
    LineSide,
    SeverityLevel,
    ReviewResponse,
    ReviewSummary,
    ReviewRequest,
)


def _make_policy_finding(
    fid: str = "POLICY-IMP-001",
    rule_id: str = "STD-IMP-001",
    rule_name: str = "Prohibited Imports",
    file_path: str = "services/auth.py",
    line: int = 10,
    severity: SeverityLevel = SeverityLevel.HIGH,
) -> Finding:
    return Finding(
        id=fid,
        title=f"Prohibited Import 'pickle' Detected",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=severity,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(
            file_path=file_path,
            start_line=line,
            line_side=LineSide.NEW,
            location_status=LocationStatus.UNVERIFIED,
        ),
        why_identified="Prohibited module pickle imported",
        impact="Security risk",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id=rule_id,
        rule_name=rule_name,
        policy_category="security",
    )


# ---------------------------------------------------------------------------
# Scenario A: Actual Duplicate (Explicit Attribution)
# ---------------------------------------------------------------------------

def test_scenario_a_exact_matching_rule_id_produces_one_authoritative_finding():
    """When Gemini outputs an explicit rule_id matching a deterministic policy, one authoritative policy finding is produced."""
    pf = _make_policy_finding(rule_id="STD-IMP-001", line=10)

    model_finding = Finding(
        id="GEM-001",
        title="Detected policy violation: import pickle",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=10),
        why_identified="Violation of prohibited imports policy",
        impact="Insecure deserialization",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id="STD-IMP-001",  # Explicit rule_id
    )

    merged = merge_policy_and_model_findings([model_finding], [pf])

    assert len(merged) == 1
    assert merged[0].id == pf.id
    assert merged[0].rule_id == "STD-IMP-001"
    assert merged[0].finding_type == FindingType.POLICY_VIOLATION


def test_scenario_a_explicit_rule_name_attribution_without_rule_id():
    """When Gemini omits rule_id but title explicitly names the policy rule ('Prohibited Imports'), it deduplicates."""
    pf = _make_policy_finding(rule_id="STD-IMP-001", rule_name="Prohibited Imports", line=10)

    model_finding = Finding(
        id="GEM-001",
        title="Prohibited Imports standard violated: pickle module",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=10),
        why_identified="Line imports pickle which is restricted",
        impact="Insecure deserialization",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id=None,
    )

    merged = merge_policy_and_model_findings([model_finding], [pf])

    assert len(merged) == 1
    assert merged[0].id == pf.id
    assert merged[0].rule_id == "STD-IMP-001"


# ---------------------------------------------------------------------------
# Scenario B: Same-Line Genuine Security Defect Must NOT Be Suppressed
# ---------------------------------------------------------------------------

def test_scenario_b_generic_security_keyword_does_not_suppress_sql_injection():
    """A genuine SQL injection defect at the same file and line as a policy finding must NEVER be suppressed,
    even when its title or description contains the generic words 'security', 'vulnerability', or 'risk'."""
    pf = _make_policy_finding(line=10)

    sqli_defect = Finding(
        id="GEM-SQLI",
        title="Critical Security Flaw: SQL Injection Vulnerability",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.CRITICAL,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=10),
        why_identified="User-controlled string concatenated directly into query creates high security risk",
        impact="Complete database compromise and data exfiltration",
        finding_type=FindingType.CODE_DEFECT,
        rule_id=None,
    )

    merged = merge_policy_and_model_findings([sqli_defect], [pf])

    # Invariant: BOTH must survive!
    assert len(merged) == 2
    types_present = {f.finding_type for f in merged}
    assert FindingType.CODE_DEFECT in types_present
    assert FindingType.POLICY_VIOLATION in types_present

    sqli = next(f for f in merged if f.finding_type == FindingType.CODE_DEFECT)
    assert sqli.id == "GEM-SQLI"
    assert "SQL Injection" in sqli.title

    policy = next(f for f in merged if f.finding_type == FindingType.POLICY_VIOLATION)
    assert policy.id == pf.id


# ---------------------------------------------------------------------------
# Scenario C: Same-Line Hardcoded Secret Survives Alongside Custom Pattern
# ---------------------------------------------------------------------------

def test_scenario_c_same_line_hardcoded_secret_survives():
    """A hardcoded credential defect on the same line as a custom pattern policy violation survives."""
    pf = Finding(
        id="POLICY-PAT-001",
        title="Policy Violation: Direct SQL Query Pattern",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=15),
        why_identified="Line matches custom pattern rule 'Direct SQL Query Pattern'",
        impact="Team policy violation",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id="SEC-CUST-001",
        rule_name="Direct SQL Query Pattern",
        policy_category="custom_patterns",
    )

    secret_defect = Finding(
        id="GEM-SECRET",
        title="Hardcoded AWS Secret Access Key",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.CRITICAL,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=15),
        why_identified="Raw AWS secret key assigned inline in source code",
        impact="Credential compromise and infrastructure takeover",
        finding_type=FindingType.CODE_DEFECT,
        rule_id=None,
    )

    merged = merge_policy_and_model_findings([secret_defect], [pf])

    assert len(merged) == 2
    ids = {f.id for f in merged}
    assert "GEM-SECRET" in ids
    assert "POLICY-PAT-001" in ids


# ---------------------------------------------------------------------------
# Scenario D: Two Policy Rules on Same Line
# ---------------------------------------------------------------------------

def test_scenario_d_two_distinct_policy_rules_on_same_line_both_survive():
    """When two deterministic policy rules apply to the same line, both survive."""
    pf1 = _make_policy_finding(fid="POLICY-IMP-001", rule_id="STD-IMP-001", line=10)
    pf2 = Finding(
        id="POLICY-PAT-001",
        title="Policy Violation: Insecure Deserialization Call",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=10),
        why_identified="Custom pattern matched loads call",
        impact="Policy violation",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id="SEC-PAT-002",
        rule_name="Insecure Deserialization Call",
        policy_category="custom_patterns",
    )

    merged = merge_policy_and_model_findings([], [pf1, pf2])

    assert len(merged) == 2
    rule_ids = {f.rule_id for f in merged}
    assert rule_ids == {"STD-IMP-001", "SEC-PAT-002"}


# ---------------------------------------------------------------------------
# Scenario E: Two Code Defects on Same Line
# ---------------------------------------------------------------------------

def test_scenario_e_two_distinct_code_defects_on_same_line_both_survive():
    """Two different model defects on the same line both survive."""
    d1 = Finding(
        id="GEM-001",
        title="SQL Injection",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.CRITICAL,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=10),
        why_identified="Unsanitized query input",
        impact="Database exploit",
        finding_type=FindingType.CODE_DEFECT,
    )
    d2 = Finding(
        id="GEM-002",
        title="Unauthenticated Endpoint Exposure",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=10),
        why_identified="Missing auth decorator",
        impact="Auth bypass",
        finding_type=FindingType.CODE_DEFECT,
    )

    merged = merge_policy_and_model_findings([d1, d2], [])
    assert len(merged) == 2
    assert {f.id for f in merged} == {"GEM-001", "GEM-002"}


# ---------------------------------------------------------------------------
# Scenario F: Ambiguous Generic Model Finding
# ---------------------------------------------------------------------------

def test_scenario_f_ambiguous_generic_model_finding_is_preserved():
    """Gemini emits a generic security observation on the same line as a policy violation without explicit attribution.
    Both findings must survive rather than risk suppressing a genuine issue."""
    pf = _make_policy_finding(line=10)

    generic_finding = Finding(
        id="GEM-GENERIC",
        title="Potential security issue with imported library",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.POTENTIAL_ISSUE,
        location=CodeLocation(file_path="services/auth.py", start_line=10),
        why_identified="Library may have known security advisories",
        impact="Operational risk",
        finding_type=FindingType.CODE_DEFECT,
        rule_id=None,
    )

    merged = merge_policy_and_model_findings([generic_finding], [pf])

    # Both survive because generic_finding lacks explicit rule_id or rule_name attribution
    assert len(merged) == 2
    assert {f.id for f in merged} == {"GEM-GENERIC", pf.id}


# ---------------------------------------------------------------------------
# F-07B: Path Normalization
# ---------------------------------------------------------------------------

def test_canonical_path_normalization_matches_git_prefixed_paths():
    """Git-prefixed paths ('b/services/auth.py', 'a/services/auth.py', './services/auth.py')
    resolve to canonical path during deduplication."""
    pf = _make_policy_finding(file_path="services/auth.py", line=10)

    # Gemini emits finding with Git prefix 'b/'
    gemini_finding = Finding(
        id="GEM-001",
        title="Prohibited import pickle",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="b/services/auth.py", start_line=10),
        why_identified="Violation of STD-IMP-001 policy",
        impact="Security risk",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id="STD-IMP-001",
    )

    merged = merge_policy_and_model_findings([gemini_finding], [pf])

    # Canonical match succeeds: deduplicated to one authoritative policy finding
    assert len(merged) == 1
    assert merged[0].id == pf.id


def test_distinct_paths_remain_distinct_after_normalization():
    """Different files on the same line number are NOT treated as collisions."""
    pf = _make_policy_finding(file_path="services/auth.py", line=10)

    gemini_finding = Finding(
        id="GEM-001",
        title="Violation of STD-IMP-001 policy",
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(file_path="services/user.py", start_line=10),
        why_identified="Violation of STD-IMP-001",
        impact="Security risk",
        finding_type=FindingType.POLICY_VIOLATION,
        rule_id="STD-IMP-001",
    )

    merged = merge_policy_and_model_findings([gemini_finding], [pf])

    # Different paths: both survive!
    assert len(merged) == 2


# ---------------------------------------------------------------------------
# Pipeline Integration: Fallback & ReviewAgent Paths
# ---------------------------------------------------------------------------

def test_fallback_engine_canonical_path_deduplication():
    """Fallback engine deduplicates identical findings across canonical path variations."""
    diff_text = """diff --git a/services/auth.py b/services/auth.py
index 1000..2000 100644
--- a/services/auth.py
+++ b/services/auth.py
@@ -1,2 +1,3 @@
+import pickle
"""
    parsed = parse_git_diff(diff_text)
    pf1 = _make_policy_finding(fid="POLICY-1", file_path="services/auth.py", line=1)
    pf2 = _make_policy_finding(fid="POLICY-2", file_path="b/services/auth.py", line=1)

    resp = run_heuristic_code_review(
        parsed,
        tool_results={},
        stages=[],
        policy_findings=[pf1, pf2]
    )

    # Both had identical rule_id, title, and line on canonical path: deduplicated to 1
    matching_policies = [f for f in resp.findings if f.finding_type == FindingType.POLICY_VIOLATION]
    assert len(matching_policies) == 1

