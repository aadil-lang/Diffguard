"""
Data schemas and domain models for DiffGuard.
All models use Pydantic v2 with strict validation and serialisation.
"""

from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingCategory(str, Enum):
    BUG_OR_LOGIC_ERROR = "BUG_OR_LOGIC_ERROR"
    SECURITY_AND_RELIABILITY = "SECURITY_AND_RELIABILITY"
    MISSING_TEST_COVERAGE = "MISSING_TEST_COVERAGE"
    CODE_QUALITY_AND_MAINTAINABILITY = "CODE_QUALITY_AND_MAINTAINABILITY"
    STYLE_AND_CONSISTENCY = "STYLE_AND_CONSISTENCY"


class FindingConfidence(str, Enum):
    CONFIRMED_ISSUE = "CONFIRMED_ISSUE"
    POTENTIAL_ISSUE = "POTENTIAL_ISSUE"
    IMPROVEMENT_SUGGESTION = "IMPROVEMENT_SUGGESTION"


class FindingType(str, Enum):
    CODE_DEFECT = "code_defect"
    POLICY_VIOLATION = "policy_violation"
    RECOMMENDATION = "recommendation"


class PolicyEvaluationStatus(str, Enum):
    VIOLATED = "violated"
    PASSED = "passed"
    NOT_EVALUATED = "not_evaluated"


class LocationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    INVALID = "invalid"
    FILE_LEVEL = "file_level"


class LineSide(str, Enum):
    NEW = "new"
    OLD = "old"
    BOTH = "both"
    FILE_LEVEL = "file_level"


class CodeLocation(BaseModel):
    file_path: str = Field(..., description="Target file path relative to repo root")
    start_line: int = Field(..., description="Line number where issue begins")
    end_line: Optional[int] = Field(None, description="Line number where issue ends")
    hunk_header: Optional[str] = Field(None, description="Hunk header context (e.g. @@ -12,4 +12,6 @@)")
    code_context: Optional[str] = Field(None, description="Contextual snippet of affected diff lines")
    line_side: Optional[LineSide] = Field(LineSide.NEW, description="Side of diff: 'new' (added), 'old' (deleted), 'both' (context), or 'file_level'")
    location_status: LocationStatus = Field(LocationStatus.UNVERIFIED, description="Location validity: verified, unverified, invalid, or file_level")
    validation_note: Optional[str] = Field(None, description="Explanation of location verification status")


class SuggestedFix(BaseModel):
    description: str = Field(..., description="Explanation of how to remediate the issue")
    replacement_code: Optional[str] = Field(None, description="Concrete proposed replacement code")
    diff_patch: Optional[str] = Field(None, description="Unified diff patch illustrating the fix")


class Finding(BaseModel):
    id: str = Field(..., description="Unique finding identifier (e.g. DG-001)")
    title: str = Field(..., description="Concise, descriptive title of the finding")
    category: FindingCategory = Field(..., description="Functional classification of the issue")
    severity: SeverityLevel = Field(..., description="Severity impact rating")
    confidence: FindingConfidence = Field(..., description="Confidence classification")
    location: CodeLocation = Field(..., description="Precise file and line location")
    why_identified: str = Field(..., description="Root-cause explanation: why is this an issue?")
    impact: str = Field(..., description="Potential consequence or operational failure risk")
    suggested_fix: Optional[SuggestedFix] = Field(None, description="Actionable proposed fix")
    tool_evidence: List[str] = Field(default_factory=list, description="Empirical evidence from tool checks")
    finding_type: FindingType = Field(default=FindingType.CODE_DEFECT, description="Classification of finding: 'code_defect', 'policy_violation', or 'recommendation'")
    rule_id: Optional[str] = Field(None, description="Identifier of the engineering standard rule (e.g. POLICY-SEC-001, STD-LEN-001)")
    rule_name: Optional[str] = Field(None, description="Human-readable rule name")
    policy_category: Optional[str] = Field(None, description="Configured policy group: code_quality, security, testing, style")
    policy_evaluation_status: Optional[PolicyEvaluationStatus] = Field(None, description="Status of policy evaluation: 'violated', 'passed', 'not_evaluated'")


ReviewVerdict = Literal["APPROVED", "APPROVED_WITH_COMMENTS", "CHANGES_REQUESTED", "CRITICAL_BLOCKER"]


class ReviewSummary(BaseModel):
    total_findings: int = 0
    total_defects: int = 0
    total_policy_violations: int = 0
    total_recommendations: int = 0
    by_finding_type: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)
    by_confidence: Dict[str, int] = Field(default_factory=dict)
    verdict: ReviewVerdict = "APPROVED"
    key_takeaways: List[str] = Field(default_factory=list)


class StageStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ProcessingStage(BaseModel):
    stage_id: str
    name: str
    status: StageStatus = StageStatus.PENDING
    details: Optional[str] = None
    duration_ms: Optional[int] = None


class ReviewRequest(BaseModel):
    diff_content: str = Field(..., min_length=5, description="Unified git diff or patch text")
    title: Optional[str] = Field(None, description="Optional title or PR name")
    custom_instructions: Optional[str] = Field(None, description="Optional custom review guidelines")
    standards_yaml: Optional[str] = Field(None, description="Optional raw YAML string conforming to .diffguard.yaml schema")
    api_key: Optional[str] = Field(None, description="Optional custom Gemini API key for this request")
    model_name: Optional[str] = Field(None, description="Optional model override")


class ReviewResponse(BaseModel):
    review_id: str
    timestamp: str
    parsed_files_count: int
    total_additions: int
    total_deletions: int
    summary: ReviewSummary
    findings: List[Finding]
    stages_executed: List[ProcessingStage]
    engine_used: str


class SampleDiff(BaseModel):
    id: str
    title: str
    description: str
    category_highlight: str
    expected_severity: SeverityLevel
    diff_content: str

