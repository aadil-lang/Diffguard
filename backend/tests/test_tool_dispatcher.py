"""
Comprehensive unit and governance tests for Gemini Tool Registry & Secure Dispatcher (Phase 2.1).
Covers all 15 required offline test scenarios without live Gemini API calls.
"""

import json
import pytest
from app.parser.diff_parser import parse_git_diff
from app.tools.tool_declarations import get_gemini_tools
from app.tools.tool_dispatcher import ToolDispatcher
from app.tools.tool_schemas import ToolResult, InspectDiffHunkArgs, InspectPatchContextArgs
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH, SAMPLE_LOGIC_ASYNC_BUG


@pytest.fixture
def sample_sqli_parsed():
    return parse_git_diff(SAMPLE_SQLI_AUTH.diff_content)


@pytest.fixture
def sample_multi_file_parsed():
    return parse_git_diff(SAMPLE_LOGIC_ASYNC_BUG.diff_content)


# 1. Tool declaration construction
def test_tool_declaration_construction():
    tools = get_gemini_tools()
    assert len(tools) >= 1
    assert hasattr(tools[0], "function_declarations")
    decls = tools[0].function_declarations
    assert len(decls) == 2
    decl_names = {d.name for d in decls}
    assert "inspect_diff_hunk" in decl_names
    assert "inspect_patch_context" in decl_names

    hunk_decl = next(d for d in decls if d.name == "inspect_diff_hunk")
    assert "file_path" in hunk_decl.parameters.properties
    assert "hunk_index" in hunk_decl.parameters.properties
    assert "file_path" in hunk_decl.parameters.required


# 2. Valid inspect_diff_hunk invocation
def test_valid_inspect_diff_hunk(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    res = dispatcher.dispatch(
        "inspect_diff_hunk",
        {"file_path": "services/auth_service.py", "hunk_index": 0}
    )
    assert res.success is True
    assert res.tool_name == "inspect_diff_hunk"
    assert res.result is not None
    assert res.result["canonical_file_path"] == "services/auth_service.py"
    assert res.result["hunk_index"] == 0
    assert len(res.result["added_lines"]) > 0
    assert "JWT_SECRET_KEY" in res.result["raw_hunk"]
    assert "raw_query = f\"SELECT id, email, role" in res.result["raw_hunk"]


# 3. Invalid file path
def test_invalid_file_path(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    res = dispatcher.dispatch(
        "inspect_diff_hunk",
        {"file_path": "completely/nonexistent/file.py", "hunk_index": 0}
    )
    assert res.success is False
    assert res.error_code == "FILE_NOT_FOUND"
    assert "not found" in (res.error_message or "").lower()


# 4. Invalid hunk index
def test_invalid_hunk_index(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    res = dispatcher.dispatch(
        "inspect_diff_hunk",
        {"file_path": "services/auth_service.py", "hunk_index": 999}
    )
    assert res.success is False
    assert res.error_code == "INVALID_HUNK_INDEX"
    assert "out of range" in (res.error_message or "").lower()


# 5. Valid inspect_patch_context invocation
def test_valid_inspect_patch_context(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    res = dispatcher.dispatch(
        "inspect_patch_context",
        {"file_path": "services/auth_service.py", "start_line": 20, "end_line": 24, "line_side": "new"}
    )
    assert res.success is True
    assert res.tool_name == "inspect_patch_context"
    assert res.result["available_in_patch"] is True
    assert res.result["lines_found"] >= 1
    assert any("raw_query = f\"SELECT id, email, role" in l["content"] for l in res.result["lines"])


# 6. Context outside supplied patch
def test_context_outside_supplied_patch(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    # Line 500 is far outside the patch hunks
    res = dispatcher.dispatch(
        "inspect_patch_context",
        {"file_path": "services/auth_service.py", "start_line": 500, "end_line": 510, "line_side": "new"}
    )
    assert res.success is True  # Tool executed successfully, returning structured limitation
    assert res.result["available_in_patch"] is False
    assert res.result["lines_found"] == 0
    assert "fall outside all patch hunks" in res.result["limitation"]


# 7. Malformed arguments (wrong type / invalid JSON)
def test_malformed_arguments_handling(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    # Passing a string that is not JSON
    res1 = dispatcher.dispatch("inspect_diff_hunk", "{invalid_json: true")
    assert res1.success is False
    assert res1.error_code == "INVALID_ARGUMENTS"

    # Passing negative hunk_index (violates ge=0 constraint)
    res2 = dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": -1})
    assert res2.success is False
    assert res2.error_code == "INVALID_ARGUMENTS"

    # Passing end_line < start_line
    res3 = dispatcher.dispatch("inspect_patch_context", {"file_path": "services/auth_service.py", "start_line": 20, "end_line": 10})
    assert res3.success is False
    assert res3.error_code == "INVALID_LINE_RANGE"


# 8. Unknown tool rejection
def test_unknown_tool_rejection(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    res = dispatcher.dispatch("execute_shell_command", {"command": "ls -la"})
    assert res.success is False
    assert res.error_code == "UNKNOWN_TOOL"
    assert "not authorized" in (res.error_message or "")


# 9. Missing required parameters
def test_missing_required_parameters(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    # inspect_diff_hunk requires file_path
    res = dispatcher.dispatch("inspect_diff_hunk", {})
    assert res.success is False
    assert res.error_code == "INVALID_ARGUMENTS"
    assert "file_path" in (res.error_message or "")


# 10. Output JSON serialization
def test_output_json_serialization(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    res = dispatcher.dispatch(
        "inspect_diff_hunk",
        {"file_path": "services/auth_service.py", "hunk_index": 0}
    )
    # Must serialize completely via json.dumps without error
    dumped = json.dumps(res.model_dump())
    assert isinstance(dumped, str)
    loaded = json.loads(dumped)
    assert loaded["success"] is True
    assert loaded["tool_name"] == "inspect_diff_hunk"

    # Must also convert to google.genai Part
    part = dispatcher.to_function_response_part("inspect_diff_hunk", res)
    assert hasattr(part, "function_response")
    assert part.function_response.name == "inspect_diff_hunk"


# 11. Output size limits
def test_output_size_limits(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    # Range of 500 lines will be safely clamped to MAX_LINE_RANGE_SPAN (50)
    res = dispatcher.dispatch(
        "inspect_patch_context",
        {"file_path": "services/auth_service.py", "start_line": 1, "end_line": 500}
    )
    assert res.success is True
    assert res.result["range_clamped"] is True
    assert res.result["requested_range"]["end_line"] == 51


# 12. Duplicate invocation caching
def test_duplicate_invocation_caching(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    args = {"file_path": "services/auth_service.py", "hunk_index": 0}
    res1 = dispatcher.dispatch("inspect_diff_hunk", args)
    assert res1.cached is False
    assert dispatcher.calls_count == 1

    # Exact duplicate call is served from cache and consumes 1 invocation attempt
    res2 = dispatcher.dispatch("inspect_diff_hunk", args)
    assert res2.cached is True
    assert dispatcher.calls_count == 2
    assert res2.result == res1.result


# 12b. Consistent invocation accounting (F-05)
def test_unknown_tool_consumes_one_attempt(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    res = dispatcher.dispatch("non_existent_tool", {})
    assert res.success is False
    assert res.error_code == "UNKNOWN_TOOL"
    assert dispatcher.calls_count == 1


def test_invalid_arguments_consume_one_attempt(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    # Negative hunk_index fails Pydantic validation
    res = dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": -5})
    assert res.success is False
    assert res.error_code == "INVALID_ARGUMENTS"
    assert dispatcher.calls_count == 1


def test_malformed_arguments_consume_one_attempt(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed)
    # Malformed non-JSON string
    res = dispatcher.dispatch("inspect_diff_hunk", "{bad_json: unquoted")
    assert res.success is False
    assert res.error_code == "INVALID_ARGUMENTS"
    assert dispatcher.calls_count == 1


def test_budget_rejection_at_limit(sample_sqli_parsed):
    dispatcher = ToolDispatcher(sample_sqli_parsed, max_tool_calls=6)
    # Perform 6 attempted calls of various types
    dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0}) # 1: success
    dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0}) # 2: cache hit
    dispatcher.dispatch("unknown_tool", {})                                                               # 3: unknown
    dispatcher.dispatch("inspect_diff_hunk", "{invalid json")                                            # 4: malformed
    dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": -1})# 5: invalid args
    dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0}) # 6: cache hit

    assert dispatcher.calls_count == 6

    # 7th attempt is rejected with BUDGET_EXCEEDED and does not increment calls_count
    res7 = dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0})
    assert res7.success is False
    assert res7.error_code == "BUDGET_EXCEEDED"
    assert dispatcher.calls_count == 6


# 13. Tool-call budget enforcement
def test_tool_call_budget_enforcement(sample_multi_file_parsed):
    dispatcher = ToolDispatcher(sample_multi_file_parsed, max_tool_calls=3)

    # 3 distinct calls
    r1 = dispatcher.dispatch("inspect_diff_hunk", {"file_path": "payments/processor.py", "hunk_index": 0})
    r2 = dispatcher.dispatch("inspect_patch_context", {"file_path": "payments/processor.py", "start_line": 10})
    r3 = dispatcher.dispatch("inspect_patch_context", {"file_path": "payments/processor.py", "start_line": 20})

    assert r1.success is True
    assert r2.success is True
    assert r3.success is True
    assert dispatcher.calls_count == 3

    # 4th call must be blocked by budget
    r4 = dispatcher.dispatch("inspect_patch_context", {"file_path": "payments/processor.py", "start_line": 30})
    assert r4.success is False
    assert r4.error_code == "BUDGET_EXCEEDED"
    assert "budget" in (r4.error_message or "").lower()
    assert dispatcher.calls_count == 3  # Did not increment beyond cap


# 14. Multiple calls sharing the same budget
def test_multiple_calls_sharing_same_budget(sample_multi_file_parsed):
    dispatcher = ToolDispatcher(sample_multi_file_parsed, max_tool_calls=4)
    for i in range(1, 5):
        res = dispatcher.dispatch("inspect_patch_context", {"file_path": "payments/processor.py", "start_line": i * 10})
        assert res.success is True
        assert dispatcher.calls_count == i

    # Next call exceeds
    res_exceeded = dispatcher.dispatch("inspect_diff_hunk", {"file_path": "payments/processor.py", "hunk_index": 0})
    assert res_exceeded.success is False
    assert res_exceeded.error_code == "BUDGET_EXCEEDED"


# 15. Read-only behavior (no side effects on parsed diff or filesystem)
def test_read_only_behavior(sample_sqli_parsed):
    original_raw = sample_sqli_parsed.raw_diff
    original_hunks_len = len(sample_sqli_parsed.files[0].hunks)

    dispatcher = ToolDispatcher(sample_sqli_parsed)
    dispatcher.dispatch("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0})
    dispatcher.dispatch("inspect_patch_context", {"file_path": "services/auth_service.py", "start_line": 16})

    # Assert underlying diff structures are completely unaltered
    assert sample_sqli_parsed.raw_diff == original_raw
    assert len(sample_sqli_parsed.files[0].hunks) == original_hunks_len
