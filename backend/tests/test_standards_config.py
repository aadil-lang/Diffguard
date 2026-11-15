"""
Unit tests for .diffguard.yaml configuration schema, validation, and safe parser.
Verifies safe YAML parsing, Pydantic v2 strict validation, size limits, regex pre-compilation,
and unknown key rejection.
"""

import pytest
from app.models.schemas import SeverityLevel
from app.standards.config_schema import (
    parse_standards_config,
    get_default_standards_config,
    DiffguardConfig,
    MAX_CONFIG_SIZE_BYTES,
)


def test_default_standards_config():
    """Verify default configuration has documented structure and valid defaults."""
    cfg = get_default_standards_config()
    assert cfg.version == 1
    assert cfg.project.name == "default"
    assert cfg.standards.code_quality is not None
    assert cfg.standards.code_quality.max_function_length.value == 50
    assert cfg.standards.security.prohibited_imports.values == ["pickle", "telnetlib"]
    assert cfg.standards.testing.require_test_changes.min_additions_threshold == 8


def test_parse_none_or_empty_returns_default():
    """Passing None or whitespace returns default configuration."""
    cfg1 = parse_standards_config(None)
    cfg2 = parse_standards_config("   ")
    assert cfg1.version == 1
    assert cfg2.version == 1
    assert cfg1.project.name == "default"


def test_parse_valid_custom_yaml():
    """Verify parsing of valid complete .diffguard.yaml."""
    yaml_text = """
version: 1
project:
  name: payments-service
  description: Core payment processing service
standards:
  code_quality:
    max_function_length:
      enabled: true
      value: 45
      severity: high
    max_nesting_depth:
      enabled: true
      value: 3
      severity: medium
  security:
    prohibited_imports:
      enabled: true
      values:
        - pickle
        - telnetlib
        - subprocess
      severity: critical
    custom_patterns:
      enabled: true
      rules:
        - id: POLICY-SEC-001
          name: Prohibited debug credentials
          pattern: 'DEBUG_PASSWORD\s*='
          severity: critical
          description: Plaintext debug credentials must not be committed.
  testing:
    require_test_changes:
      enabled: true
      severity: high
      min_additions_threshold: 10
"""
    cfg = parse_standards_config(yaml_text)
    assert cfg.version == 1
    assert cfg.project.name == "payments-service"
    assert cfg.standards.code_quality.max_function_length.enabled is True
    assert cfg.standards.code_quality.max_function_length.value == 45
    assert cfg.standards.code_quality.max_function_length.severity == SeverityLevel.HIGH
    assert cfg.standards.security.prohibited_imports.values == ["pickle", "telnetlib", "subprocess"]
    assert len(cfg.standards.security.custom_patterns.rules) == 1
    assert cfg.standards.security.custom_patterns.rules[0].id == "POLICY-SEC-001"
    assert cfg.standards.testing.require_test_changes.min_additions_threshold == 10


def test_reject_unknown_configuration_keys():
    """Strict schema rejects unknown configuration keys (extra='forbid')."""
    yaml_text = """
version: 1
unknown_root_key: true
standards:
  code_quality:
    max_function_length:
      enabled: true
      value: 50
"""
    with pytest.raises(ValueError, match="extra_forbidden|Extra inputs are not permitted"):
        parse_standards_config(yaml_text)


def test_reject_malformed_yaml_syntax():
    """Malformed YAML syntax raises clear ValueError."""
    yaml_text = "version: 1\nstandards: [unclosed list"
    with pytest.raises(ValueError, match="Malformed YAML in .diffguard.yaml"):
        parse_standards_config(yaml_text)


def test_reject_non_dict_yaml_root():
    """YAML scalar or list root raises clear ValueError."""
    with pytest.raises(ValueError, match="Configuration root must be a YAML mapping"):
        parse_standards_config("- item 1\n- item 2")


def test_reject_invalid_severity():
    """Invalid severity level raises validation error."""
    yaml_text = """
version: 1
standards:
  code_quality:
    max_function_length:
      enabled: true
      value: 50
      severity: ULTRA_CRITICAL
"""
    with pytest.raises(ValueError, match="Input should be 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW' or 'INFO'"):
        parse_standards_config(yaml_text)


def test_reject_invalid_rule_id_pattern():
    """Rule IDs with spaces or invalid symbols are rejected."""
    yaml_text = """
version: 1
standards:
  security:
    custom_patterns:
      enabled: true
      rules:
        - id: "BAD ID WITH SPACES"
          name: Bad Rule
          pattern: "test"
          severity: medium
"""
    with pytest.raises(ValueError, match="must be 2-64 characters matching"):
        parse_standards_config(yaml_text)


def test_reject_invalid_regex_pattern():
    """Invalid regular expression syntax raises validation error during config load."""
    yaml_text = """
version: 1
standards:
  security:
    custom_patterns:
      enabled: true
      rules:
        - id: POLICY-01
          name: Unmatched Parenthesis
          pattern: "([unclosed_regex"
          severity: medium
"""
    with pytest.raises(ValueError, match="Invalid regular expression pattern"):
        parse_standards_config(yaml_text)


def test_reject_excessively_long_pattern():
    """Patterns exceeding 500 characters are rejected."""
    long_pat = "a" * 501
    yaml_text = f"""
version: 1
standards:
  security:
    custom_patterns:
      enabled: true
      rules:
        - id: POLICY-01
          name: Too Long
          pattern: "{long_pat}"
          severity: medium
"""
    with pytest.raises(ValueError, match="at most 500 characters"):
        parse_standards_config(yaml_text)


def test_reject_oversized_configuration_file():
    """Configuration files exceeding 64KB are rejected before parsing."""
    large_yaml = "# Padding\n" + (" " * (MAX_CONFIG_SIZE_BYTES + 10))
    with pytest.raises(ValueError, match="exceeds maximum allowed size of 64 KB"):
        parse_standards_config(large_yaml)


def test_reject_out_of_bounds_numeric_limits():
    """Negative or zero numeric bounds are rejected."""
    yaml_text = """
version: 1
standards:
  code_quality:
    max_function_length:
      enabled: true
      value: 0
"""
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        parse_standards_config(yaml_text)
