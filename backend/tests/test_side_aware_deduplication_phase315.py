"""
Phase 3.1.5 Diff-Side-Aware Finding Deduplication Regression Test Suite.
Verifies diff-side identity matching and collision protection:
- Same path, same line, same side, explicit matching rule ID -> One authoritative finding
- Same path and line, OLD vs NEW, matching rule ID -> Both findings survive
- Same path and line, OLD vs NEW, exact rule name attribution -> Both findings survive
- Same path, different lines, matching rule ID -> Both findings survive
- Different paths, same line, matching rule ID -> Both findings survive
- Same path and line, different policy rule IDs -> Both policy findings survive
- Same path and line, ambiguous model finding -> Both findings survive
- Missing side information -> Conservative behavior (both survive)
- File-level findings -> Preserved semantics (file-level matches file-level, not line-level)
- Fallback engine parity -> OLD and NEW sides do not collide in fallback
"""

import pytest
from app.agent.reviewer_agent import ReviewAgent, merge_policy_and_model_findings, are_line_sides_compatible
from app.agent.fallback_engine import run_heuristic_code_review
from app.parser.diff_parser import parse_git_diff
from app.models.schemas import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingType,
    CodeLocation,
    LocationStatus,
    LineSide,
    SeverityLevel,
)


def _make_finding(
    fid: str,
    title: str,
    file_path: str = "services/auth.py",
    line: int = 10,
    side: LineSide = LineSide.NEW,
    rule_id: str = None,
    rule_name: str = None,
    finding_type: FindingType = FindingType.POLICY_VIOLATION,
    why: str = "Policy violation",
) -> Finding:
    return Finding(
        id=fid,
        title=title,
        category=FindingCategory.SECURITY_AND_RELIABILITY,
        severity=SeverityLevel.HIGH,
        confidence=FindingConfidence.CONFIRMED_ISSUE,
        location=CodeLocation(
            file_path=file_path,
            start_line=line,
            line_side=side,
            location_status=LocationStatus.UNVERIFIED,
        ),
        why_identified=why,
        impact="Security risk",
        finding_type=finding_type,
        rule_id=rule_id,
        rule_name=rule_name,
        policy_category="security",
    )


# ---------------------------------------------------------------------------
# Direct Unit Verification of are_line_sides_compatible()
# ---------------------------------------------------------------------------

def test_are_line_sides_compatible_unit():
    """Verify exact compatibility matrix for diff sides."""
    # Compatible cases
    assert are_line_sides_compatible(LineSide.NEW, LineSide.NEW) is True
    assert are_line_sides_compatible(LineSide.OLD, LineSide.OLD) is True
    assert are_line_sides_compatible(LineSide.BOTH, LineSide.BOTH) is True
    assert are_line_sides_compatible(LineSide.FILE_LEVEL, LineSide.FILE_LEVEL) is True
    assert are_line_sides_compatible("new", "new") is True

    # Incompatible: OLD vs NEW
    assert are_line_sides_compatible(LineSide.OLD, LineSide.NEW) is False
    assert are_line_sides_compatible(LineSide.NEW, LineSide.OLD) is False

    # Incompatible: File-level vs line-level
    assert are_line_sides_compatible(LineSide.FILE_LEVEL, LineSide.NEW) is False
    assert are_line_sides_compatible(LineSide.NEW, LineSide.FILE_LEVEL) is False
    assert are_line_sides_compatible(LineSide.FILE_LEVEL, LineSide.OLD) is False

    # Incompatible: Context (BOTH) vs Added (NEW) / Deleted (OLD)
    assert are_line_sides_compatible(LineSide.BOTH, LineSide.NEW) is False
    assert are_line_sides_compatible(LineSide.NEW, LineSide.BOTH) is False

    # Incompatible: Missing side information (conservative matching)
    assert are_line_sides_compatible(None, LineSide.NEW) is False
    assert are_line_sides_compatible(LineSide.NEW, None) is False
    assert are_line_sides_compatible(None, None) is False
    assert are_line_sides_compatible("invalid_side", LineSide.NEW) is False


# ---------------------------------------------------------------------------
# Scenario 1: Same Path, Same Line, Same Side, Matching Rule ID
# ---------------------------------------------------------------------------

def test_same_path_same_line_same_side_explicit_rule_id():
    """When path, line, side (NEW/NEW), and rule_id match, deduplicates to 1 authoritative policy finding."""
    pf = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
        rule_name="Prohibited Imports"
    )
    mf = _make_finding(
        fid="GEM-001",
        title="Policy standard STD-IMP-001 violated",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
        finding_type=FindingType.POLICY_VIOLATION
    )

    merged = merge_policy_and_model_findings([mf], [pf])
    assert len(merged) == 1
    assert merged[0].id == "POLICY-IMP-001"
    assert merged[0].location.line_side == LineSide.NEW


# ---------------------------------------------------------------------------
# Scenario 2: Same Path and Line, OLD vs NEW, Matching Rule ID
# ---------------------------------------------------------------------------

def test_same_path_line_old_vs_new_matching_rule_id():
    """Findings on OLD vs NEW side on the same numeric line number must NEVER be collapsed,
    even when they carry the same rule_id."""
    pf = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
        rule_name="Prohibited Imports"
    )
    # Model reports a finding on the deleted/old version of line 10
    mf = _make_finding(
        fid="GEM-001",
        title="Old code on deleted line violated STD-IMP-001",
        line=10,
        side=LineSide.OLD,
        rule_id="STD-IMP-001",
        finding_type=FindingType.POLICY_VIOLATION
    )

    merged = merge_policy_and_model_findings([mf], [pf])

    # Invariant: BOTH must survive because they refer to different code versions!
    assert len(merged) == 2
    sides_present = {f.location.line_side for f in merged}
    assert LineSide.OLD in sides_present
    assert LineSide.NEW in sides_present


# ---------------------------------------------------------------------------
# Scenario 3: Same Path and Line, OLD vs NEW, Exact Rule Name Attribution
# ---------------------------------------------------------------------------

def test_same_path_line_old_vs_new_exact_rule_name():
    """OLD vs NEW findings must not collapse when attribution is based on rule name in text."""
    pf = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
        rule_name="Prohibited Imports"
    )
    mf = _make_finding(
        fid="GEM-001",
        title="Deleted line violates Prohibited Imports standard",
        line=10,
        side=LineSide.OLD,
        rule_id=None,
        finding_type=FindingType.CODE_DEFECT,
        why="Prohibited Imports policy violation"
    )

    merged = merge_policy_and_model_findings([mf], [pf])

    assert len(merged) == 2
    sides = {f.location.line_side for f in merged}
    assert LineSide.OLD in sides
    assert LineSide.NEW in sides


# ---------------------------------------------------------------------------
# Scenario 4: Same Path, Different Lines, Matching Rule ID
# ---------------------------------------------------------------------------

def test_same_path_diff_lines_matching_rule_id():
    """Same rule ID on different lines in the same file must both survive."""
    pf = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
    )
    mf = _make_finding(
        fid="GEM-001",
        title="Another prohibited import",
        line=25,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
    )

    merged = merge_policy_and_model_findings([mf], [pf])
    assert len(merged) == 2
    lines = {f.location.start_line for f in merged}
    assert lines == {10, 25}


# ---------------------------------------------------------------------------
# Scenario 5: Different Paths, Same Line, Matching Rule ID
# ---------------------------------------------------------------------------

def test_diff_paths_same_line_matching_rule_id():
    """Same rule ID in different files must both survive."""
    pf = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        file_path="services/auth.py",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
    )
    mf = _make_finding(
        fid="GEM-001",
        title="Prohibited import in payments",
        file_path="services/payments.py",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
    )

    merged = merge_policy_and_model_findings([mf], [pf])
    assert len(merged) == 2
    paths = {f.location.file_path for f in merged}
    assert paths == {"services/auth.py", "services/payments.py"}


# ---------------------------------------------------------------------------
# Scenario 6: Same Path and Line, Different Policy Rule IDs
# ---------------------------------------------------------------------------

def test_same_path_line_diff_policy_rules():
    """Two different policy rules on the same line both survive."""
    pf1 = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
    )
    pf2 = _make_finding(
        fid="POLICY-PAT-001",
        title="Custom Pattern",
        line=10,
        side=LineSide.NEW,
        rule_id="SEC-CUST-001",
    )

    merged = merge_policy_and_model_findings([], [pf1, pf2])
    assert len(merged) == 2
    r_ids = {f.rule_id for f in merged}
    assert r_ids == {"STD-IMP-001", "SEC-CUST-001"}


# ---------------------------------------------------------------------------
# Scenario 7: Same Path and Line, Ambiguous Model Finding
# ---------------------------------------------------------------------------

def test_same_path_line_ambiguous_model_finding():
    """Ambiguous model finding on the same line as a policy violation survives."""
    pf = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
    )
    mf = _make_finding(
        fid="GEM-001",
        title="Generic risk on line 10",
        line=10,
        side=LineSide.NEW,
        rule_id=None,
        finding_type=FindingType.CODE_DEFECT,
        why="Potential unvetted dependency usage"
    )

    merged = merge_policy_and_model_findings([mf], [pf])
    assert len(merged) == 2
    ids = {f.id for f in merged}
    assert ids == {"GEM-001", "POLICY-IMP-001"}


# ---------------------------------------------------------------------------
# Scenario 8: Missing Side Information (Conservative Matching)
# ---------------------------------------------------------------------------

def test_missing_model_side_conservative_behavior():
    """When model finding has line_side=None, conservative matching preserves both findings."""
    pf = _make_finding(
        fid="POLICY-IMP-001",
        title="Prohibited Import 'pickle' Detected",
        line=10,
        side=LineSide.NEW,
        rule_id="STD-IMP-001",
    )
    # Model location with line_side=None
    mf = _make_finding(
        fid="GEM-001",
        title="STD-IMP-001 violation",
        line=10,
        side=None,
        rule_id="STD-IMP-001",
    )
    mf.location.line_side = None

    merged = merge_policy_and_model_findings([mf], [pf])

    # Conservative: cannot establish that they are the same version of the line without guessing -> both survive
    assert len(merged) == 2
    ids = {f.id for f in merged}
    assert ids == {"GEM-001", "POLICY-IMP-001"}


# ---------------------------------------------------------------------------
# Scenario 9: File-Level Finding Scoping
# ---------------------------------------------------------------------------

def test_file_level_findings_compatibility():
    """Two file-level findings with matching rule_id deduplicate to 1 file-level finding."""
    pf = _make_finding(
        fid="POLICY-TEST-001",
        title="No Corresponding Test Changes",
        line=1,
        side=LineSide.FILE_LEVEL,
        rule_id="STD-TEST-001",
        rule_name="Require Test Changes"
    )
    mf = _make_finding(
        fid="GEM-TEST",
        title="Missing tests for this PR",
        line=1,
        side=LineSide.FILE_LEVEL,
        rule_id="STD-TEST-001",
    )

    merged = merge_policy_and_model_findings([mf], [pf])
    assert len(merged) == 1
    assert merged[0].id == "POLICY-TEST-001"
    assert merged[0].location.line_side == LineSide.FILE_LEVEL


def test_file_level_vs_line_level_incompatibility():
    """A line-level finding must NEVER be collapsed into a file-level policy finding."""
    pf = _make_finding(
        fid="POLICY-TEST-001",
        title="No Corresponding Test Changes",
        line=1,
        side=LineSide.FILE_LEVEL,
        rule_id="STD-TEST-001",
    )
    mf = _make_finding(
        fid="GEM-001",
        title="Missing assertion on line 1",
        line=1,
        side=LineSide.NEW,
        rule_id="STD-TEST-001",
        finding_type=FindingType.CODE_DEFECT
    )

    merged = merge_policy_and_model_findings([mf], [pf])
    # Both survive because one is line-specific and one is file-level
    assert len(merged) == 2
    sides = {f.location.line_side for f in merged}
    assert sides == {LineSide.FILE_LEVEL, LineSide.NEW}


# ---------------------------------------------------------------------------
# Fallback Engine Side-Aware Parity
# ---------------------------------------------------------------------------

def test_fallback_engine_side_aware_deduplication():
    """Deterministic fallback engine does not collapse OLD and NEW side findings with same line number."""
    diff_text = """diff --git a/services/auth.py b/services/auth.py
index 1000..2000 100644
--- a/services/auth.py
+++ b/services/auth.py
@@ -1,2 +1,2 @@
-import old_pickle
+import new_pickle
"""
    parsed = parse_git_diff(diff_text)

    # Simulated finding on deleted line 1 (OLD)
    old_f = _make_finding(
        fid="OLD-001",
        title="Insecure Old Import",
        line=1,
        side=LineSide.OLD,
        rule_id="STD-IMP-001"
    )
    # Simulated policy finding on added line 1 (NEW)
    new_f = _make_finding(
        fid="NEW-001",
        title="Prohibited Import 'new_pickle' Detected",
        line=1,
        side=LineSide.NEW,
        rule_id="STD-IMP-001"
    )

    resp = run_heuristic_code_review(
        parsed,
        tool_results={},
        stages=[],
        policy_findings=[old_f, new_f]
    )

    # Both findings must survive in fallback because they are on different diff sides
    assert len(resp.findings) == 2
    sides = {f.location.line_side for f in resp.findings}
    assert LineSide.OLD in sides
    assert LineSide.NEW in sides

