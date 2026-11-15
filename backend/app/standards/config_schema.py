"""
Configuration schema and safe parser for .diffguard.yaml engineering standards.
Enforces strict Pydantic v2 validation, safe YAML loading, size limits, and regex pre-compilation.
"""

import re
import re2
from typing import List, Optional, Annotated
import yaml
from pydantic import BaseModel, Field, ConfigDict, field_validator, BeforeValidator

from app.models.schemas import SeverityLevel

MAX_CONFIG_SIZE_BYTES = 65_536  # 64 KB
MAX_REGEX_PATTERN_LENGTH = 500
RULE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,64}$")


def _normalize_severity(v: object) -> object:
    """Accepts case-insensitive severity strings ('high', 'HIGH', 'Medium') and normalizes to uppercase."""
    if isinstance(v, str):
        return v.strip().upper()
    return v


PolicySeverity = Annotated[SeverityLevel, BeforeValidator(_normalize_severity)]


class MaxFunctionLengthRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    value: int = Field(50, ge=1, le=1000, description="Maximum permitted lines in a function definition")
    severity: PolicySeverity = Field(SeverityLevel.MEDIUM, description="Violation severity")


class MaxNestingDepthRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    value: int = Field(4, ge=1, le=20, description="Maximum permitted nesting depth")
    severity: PolicySeverity = Field(SeverityLevel.MEDIUM, description="Violation severity")


class CodeQualityStandards(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_function_length: Optional[MaxFunctionLengthRule] = Field(default_factory=MaxFunctionLengthRule)
    max_nesting_depth: Optional[MaxNestingDepthRule] = Field(default_factory=MaxNestingDepthRule)


class ProhibitedImportsRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    values: List[str] = Field(default_factory=list, description="List of prohibited package/module names")
    severity: PolicySeverity = Field(SeverityLevel.HIGH, description="Violation severity")

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: List[str]) -> List[str]:
        cleaned = []
        for item in v:
            name = item.strip()
            if not name:
                continue
            if len(name) > 128:
                raise ValueError(f"Prohibited import name '{name[:30]}...' exceeds maximum length of 128 characters")
            cleaned.append(name)
        return cleaned


class CustomPatternRuleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Unique rule identifier (e.g. POLICY-SEC-001)")
    name: str = Field(..., min_length=1, max_length=128, description="Human-readable rule name")
    pattern: str = Field(..., min_length=1, max_length=MAX_REGEX_PATTERN_LENGTH, description="Regular expression pattern")
    severity: PolicySeverity = Field(SeverityLevel.HIGH, description="Violation severity")
    description: Optional[str] = Field(None, max_length=512, description="Explanation of policy rationale")

    @field_validator("id")
    @classmethod
    def validate_rule_id(cls, v: str) -> str:
        clean = v.strip()
        if not RULE_ID_PATTERN.match(clean):
            raise ValueError(f"Rule ID '{clean}' must be 2-64 characters matching [A-Za-z0-9_-]")
        return clean

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) > MAX_REGEX_PATTERN_LENGTH:
            raise ValueError(f"Regex pattern exceeds maximum length of {MAX_REGEX_PATTERN_LENGTH} characters")
        try:
            re2.compile(clean)
        except Exception as e:
            err_msg = e.args[0] if getattr(e, "args", None) else str(e)
            if isinstance(err_msg, bytes):
                err_msg = err_msg.decode("utf-8", errors="replace")
            raise ValueError(
                f"Invalid regular expression pattern '{clean}': {err_msg}. "
                "Note: DiffGuard uses Google RE2 for guaranteed linear-time matching (no backtracking, no lookaheads/backreferences)."
            )
        return clean


class CustomPatternsRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    rules: List[CustomPatternRuleItem] = Field(default_factory=list, description="List of custom pattern rules")


class SecurityStandards(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prohibited_imports: Optional[ProhibitedImportsRule] = Field(default_factory=ProhibitedImportsRule)
    custom_patterns: Optional[CustomPatternsRule] = Field(default_factory=CustomPatternsRule)


class RequireTestChangesRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    severity: PolicySeverity = Field(SeverityLevel.MEDIUM, description="Violation severity")
    min_additions_threshold: int = Field(8, ge=1, le=500, description="Minimum production additions to trigger test requirement")


class TestingStandards(BaseModel):
    __test__ = False  # Prevent pytest from collecting this model as a test class
    model_config = ConfigDict(extra="forbid")
    require_test_changes: Optional[RequireTestChangesRule] = Field(default_factory=RequireTestChangesRule)


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field("default", max_length=128)
    description: Optional[str] = Field(None, max_length=512)


class StandardsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code_quality: Optional[CodeQualityStandards] = Field(default_factory=CodeQualityStandards)
    security: Optional[SecurityStandards] = Field(default_factory=SecurityStandards)
    testing: Optional[TestingStandards] = Field(default_factory=TestingStandards)


class DiffguardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(1, ge=1, le=1, description="Configuration schema version (currently 1)")
    project: Optional[ProjectMetadata] = Field(default_factory=ProjectMetadata)
    standards: StandardsConfig = Field(default_factory=StandardsConfig)


def get_default_standards_config() -> DiffguardConfig:
    """
    Returns the baseline default configuration applied when no custom .diffguard.yaml is provided.
    All rules are documented with recommended thresholds and can be enabled via custom configuration.
    """
    return DiffguardConfig(
        version=1,
        project=ProjectMetadata(name="default"),
        standards=StandardsConfig(
            code_quality=CodeQualityStandards(
                max_function_length=MaxFunctionLengthRule(enabled=False, value=50, severity=SeverityLevel.MEDIUM),
                max_nesting_depth=MaxNestingDepthRule(enabled=False, value=4, severity=SeverityLevel.MEDIUM)
            ),
            security=SecurityStandards(
                prohibited_imports=ProhibitedImportsRule(enabled=False, values=["pickle", "telnetlib"], severity=SeverityLevel.HIGH),
                custom_patterns=CustomPatternsRule(enabled=False, rules=[])
            ),
            testing=TestingStandards(
                require_test_changes=RequireTestChangesRule(enabled=False, severity=SeverityLevel.MEDIUM, min_additions_threshold=8)
            )
        )
    )


def parse_standards_config(raw_yaml: Optional[str]) -> DiffguardConfig:
    """
    Parses and validates raw YAML string into a strict DiffguardConfig instance.
    Uses safe loading, enforces size bounds, and returns clear validation errors.
    """
    if raw_yaml is None or not raw_yaml.strip():
        return get_default_standards_config()

    raw_bytes = raw_yaml.encode("utf-8")
    if len(raw_bytes) > MAX_CONFIG_SIZE_BYTES:
        raise ValueError(f"Configuration file exceeds maximum allowed size of {MAX_CONFIG_SIZE_BYTES // 1024} KB ({len(raw_bytes)} bytes)")

    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML in .diffguard.yaml: {exc}")

    if not isinstance(data, dict):
        raise ValueError("Invalid .diffguard.yaml: Configuration root must be a YAML mapping/dictionary.")

    try:
        return DiffguardConfig.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Invalid .diffguard.yaml configuration: {exc}")
