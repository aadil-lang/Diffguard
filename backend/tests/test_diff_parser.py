"""
Unit tests for Git Diff and Unified Patch Parser.
"""

import pytest
from app.parser.diff_parser import parse_git_diff, detect_language, clean_file_path
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH, SAMPLE_LOGIC_ASYNC_BUG


def test_detect_language():
    assert detect_language("app/main.py") == "python"
    assert detect_language("frontend/src/app.tsx") == "typescript"
    assert detect_language("server/index.js") == "javascript"
    assert detect_language("cmd/main.go") == "go"
    assert detect_language("unknown_file.xyz") == "unknown"


def test_clean_file_path():
    assert clean_file_path("a/services/auth.py") == "services/auth.py"
    assert clean_file_path("b/services/auth.py") == "services/auth.py"
    assert clean_file_path("services/auth.py") == "services/auth.py"


def test_empty_diff_handling():
    res = parse_git_diff("")
    assert res.is_valid is False
    assert "empty" in res.error_message.lower()

    res_spaces = parse_git_diff("   \n\n   ")
    assert res_spaces.is_valid is False


def test_invalid_diff_handling():
    res = parse_git_diff("This is just some random text with no patch markers.")
    assert res.is_valid is False
    assert res.error_message is not None


def test_parse_valid_sqli_sample():
    res = parse_git_diff(SAMPLE_SQLI_AUTH.diff_content)
    assert res.is_valid is True
    assert res.total_files == 1
    file_obj = res.files[0]
    assert file_obj.target_file == "services/auth_service.py"
    assert file_obj.language == "python"
    assert len(file_obj.hunks) == 1
    assert file_obj.additions > 0
    assert file_obj.deletions > 0


def test_parse_multi_file_sample():
    res = parse_git_diff(SAMPLE_LOGIC_ASYNC_BUG.diff_content)
    assert res.is_valid is True
    assert res.total_files == 2
    assert res.files[0].language == "python"
    assert res.files[1].language == "typescript"
    assert res.total_additions > 0

