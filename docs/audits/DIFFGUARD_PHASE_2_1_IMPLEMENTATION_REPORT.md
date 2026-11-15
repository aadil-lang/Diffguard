# DiffGuard — Phase 2.1 Implementation Report
## Gemini Function Calling: Tool Registry & Secure Dispatcher

**Project:** DiffGuard — AI-Powered Git Diff & Pull Request Review Agent  
**Working Directory:** `C:\Users\HP\OneDrive\Documents\Diffguard`  
**Phase:** 2.1 — Tool Registry & Secure Dispatcher Foundation  
**Date:** November 13, 2026  
**Status:** Completed & Verified  

---

## 1. Executive Summary

Phase 2.1 implements the deterministic foundation for model-directed Gemini Function Calling in DiffGuard without perturbing the existing production review pipeline.

All objectives have been implemented and verified:
1. **SDK Compatibility Verified:** Confirmed `google-genai==3.3.0` types, manual dispatch patterns, and explicit `types.Tool` constructors.
2. **Exposed Tool Set Implemented:** Built read-only, deterministic tools for hunk inspection (`inspect_diff_hunk`) and patch context extraction (`inspect_patch_context`).
3. **Strict Pydantic Argument Schemas:** Enforced validation on file paths, hunk indices, and line ranges with `extra="forbid"`.
4. **Governed Request-Scoped Dispatcher:** Implemented `ToolDispatcher` with a strict allowlist, a maximum budget of 6 calls per review, memoization / deduplication caching, and standardized JSON result envelopes.
5. **Comprehensive Offline Test Suite:** Added 15 automated regression tests in `test_tool_dispatcher.py`, bringing the total backend test suite to 67 passing tests (100% success rate).

---

## 2. Inspected SDK Version & Verified Behavior

### 2.1 Installed SDK Details
- **Package:** `google-genai`
- **Verified Installed Version:** `3.3.0`
- **Runtime Environment:** Python 3.12.7 (Windows)

### 2.2 Verified Declaration & Manual Dispatch Architecture
- **Tool Declaration:** Uses `types.Tool(function_declarations=[...])` with `types.FunctionDeclaration` and `types.Schema`. Automatic callable reflection (`types.FunctionDeclaration.from_callable`) was intentionally avoided because inspecting SDK internals reveals it accesses `client.vertexai`. Explicit declarations are completely self-contained, deterministic, and independent of client state.
- **Manual Function Dispatch:** Rather than delegating code execution to the SDK's automatic function calling loop (AFC), DiffGuard employs an application-governed manual dispatch loop.
- **Function Response Protocol:** When the model emits `types.FunctionCall`, the dispatcher executes the tool locally and formats the response as:
  ```python
  types.Part.from_function_response(name=tool_name, response=tool_result.model_dump())
  ```
  delivered within a `types.Content(role="user", parts=[...])` conversation turn.

---

## 3. Tool Registry Architecture

### 3.1 Tools Exposed to Gemini

| Tool Name | Purpose | Target Arguments | Returned Evidence |
|---|---|---|---|
| **`inspect_diff_hunk`** | Inspects specific hunk lines and metadata for a modified file. | `file_path: str`<br>`hunk_index: int = 0` | Canonical path, hunk index, total hunks, header, source/target start and length, added lines array, deleted lines array, context lines array, raw hunk text. |
| **`inspect_patch_context`** | Retrieves surrounding lines present within the submitted patch for a given line range. | `file_path: str`<br>`start_line: int`<br>`end_line: Optional[int]`<br>`line_side: Literal["new", "old", "both"] = "new"` | Canonical path, matched lines array with line numbers and change types (`+`, `-`, ` `), availability flag, and limitation note if outside hunks. |

### 3.2 Tools Deliberately Kept Internal (Baseline)
- **`analyze_test_coverage`:** Whole-diff analysis measuring modified production code vs test file presence. Kept as an internal baseline check in Stage 3 because it operates across all files simultaneously.
- **`scan_security_issues` (Batch):** Continues to run unconditionally during Stage 3 baseline analysis to guarantee that core security patterns (SQLi, hardcoded tokens, RCE) are never skipped even if the LLM fails to request them.
- **`run_syntax_and_linter_checks` (Batch):** Baseline AST check across all added hunks to seed initial syntax evidence.

---

## 4. Argument Schemas & Validation

All tool argument schemas enforce strict validation via Pydantic v2 with `extra="forbid"` in `backend/app/tools/tool_schemas.py`:

```python
class InspectDiffHunkArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str = Field(..., min_length=1, description="Relative repository file path to inspect")
    hunk_index: int = Field(0, ge=0, description="Zero-based index of the hunk within the specified file")

class InspectPatchContextArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str = Field(..., min_length=1, description="Relative repository file path to inspect")
    start_line: int = Field(..., ge=1, description="Starting 1-based line number to inspect")
    end_line: Optional[int] = Field(None, ge=1, description="Ending 1-based line number (inclusive)")
    line_side: Literal["new", "old", "both"] = Field("new", description="Diff side: 'new', 'old', or 'both'")
```

Validation guarantees:
- Unknown fields injected by the model trigger immediate `INVALID_ARGUMENTS` errors.
- Negative hunk indices (`hunk_index < 0`) or line numbers (`start_line < 1`) are rejected.
- `end_line < start_line` triggers an explicit `INVALID_LINE_RANGE` error.
- Line ranges exceeding 50 lines are safely clamped to prevent context window saturation.

---

## 5. Security & Governance Controls

The `ToolDispatcher` in `backend/app/tools/tool_dispatcher.py` implements the following security boundaries:

1. **Strict Tool Allowlist:** Only tools in `ALLOWED_TOOLS = {"inspect_diff_hunk", "inspect_patch_context"}` can execute. Requests for unknown or arbitrary functions (e.g. `execute_shell_command`) are immediately rejected with error code `UNKNOWN_TOOL`.
2. **Zero Code Execution & Read-Only Guarantee:** Tools operate exclusively in-memory on parsed `ParsedDiff` structures. No `eval()`, `exec()`, `subprocess`, file system I/O, or network sockets are used.
3. **Tool Call Budget Enforcement:** A strict maximum of 6 tool calls per review request (`DEFAULT_MAX_TOOL_CALLS = 6`). Subsequent calls are halted with `BUDGET_EXCEEDED`.
4. **Duplicate Invocation Caching:** Tool calls are memoized using a composite key `(tool_name, json.dumps(args, sort_keys=True))`. Repeated identical calls return cached results with `cached=True` and do **not** decrement the tool budget.
5. **Output Envelope & Sanitization:** All responses follow the `ToolResult` envelope (`success`, `tool_name`, `result`, `error_code`, `error_message`, `cached`). Errors contain clean descriptions without exposing internal stack traces or environment variables. Outputs exceeding 16,000 characters are safely trimmed with a truncation warning.

---

## 6. Automated Test Results

### 6.1 Dispatcher & Registry Suite (`test_tool_dispatcher.py`)
All 15 required offline test scenarios were implemented and executed:

1. `test_tool_declaration_construction`: Verified Gemini `types.Tool` with 2 valid function declarations.
2. `test_valid_inspect_diff_hunk`: Verified accurate retrieval of hunk lines and metadata.
3. `test_invalid_file_path`: Verified `FILE_NOT_FOUND` error on non-existent path.
4. `test_invalid_hunk_index`: Verified `INVALID_HUNK_INDEX` error when index $\ge$ total hunks.
5. `test_valid_inspect_patch_context`: Verified retrieval of lines matching line range and side.
6. `test_context_outside_supplied_patch`: Verified structured limitation when requested line is outside hunks.
7. `test_malformed_arguments_handling`: Verified rejection of invalid JSON, negative indices, inverted ranges.
8. `test_unknown_tool_rejection`: Verified `UNKNOWN_TOOL` on unauthorized function call.
9. `test_missing_required_parameters`: Verified `INVALID_ARGUMENTS` when required `file_path` is omitted.
10. `test_output_json_serialization`: Verified full `json.dumps()` compliance and conversion to `types.Part`.
11. `test_output_size_limits`: Verified line ranges $>50$ are clamped.
12. `test_duplicate_invocation_caching`: Verified cached responses and zero budget increment on duplicates.
13. `test_tool_call_budget_enforcement`: Verified 4th call blocked when max budget is 3.
14. `test_multiple_calls_sharing_same_budget`: Verified multi-call budget accounting.
15. `test_read_only_behavior`: Verified parsed diff is not mutated by tool executions.

### 6.2 Test Execution Command & Outcome
```powershell
python -m pytest backend/tests -v
```
**Outcome: 67 passed in 2.25s (100% pass rate)**
- 15 tests in `test_tool_dispatcher.py` (NEW)
- 11 tests in `test_finding_integrity.py`
- 14 tests in `test_security_hardening.py`
- 27 existing tests across agent, parser, routes, and security adversarial suites.

Frontend tests and production build verification:
```powershell
cd frontend; npm test
```
**Outcome: 5 passed in 83ms**

---

## 7. Files Created & Modified

| File | Status | Description |
|---|---|---|
| `backend/app/tools/tool_schemas.py` | **Created** | Pydantic models for `ToolResult`, `InspectDiffHunkArgs`, and `InspectPatchContextArgs`. |
| `backend/app/tools/hunk_inspector.py` | **Created** | Deterministic in-memory implementations for hunk and patch context inspection. |
| `backend/app/tools/tool_declarations.py` | **Created** | Explicit `types.Tool` constructors and schema declarations for Gemini 2.5 Flash. |
| `backend/app/tools/tool_dispatcher.py` | **Created** | Request-scoped `ToolDispatcher` with allowlist, budget caps, caching, and error envelopes. |
| `backend/app/tools/tool_registry.py` | Modified | Exported new dispatcher, schemas, and declarations; preserved legacy batch analysis. |
| `backend/tests/test_tool_dispatcher.py` | **Created** | 15 offline tests covering all governance, validation, and error scenarios. |

---

## 8. Limitations & Phase 2.2 Outlook

- **Zero Pipeline Disruption:** `ReviewAgent.execute_review` remains completely untouched in this phase. The new dispatcher and declarations are decoupled and verified, ready to be wired into the two-phase ReAct loop during Phase 2.2.
- **Repository Visibility Boundary:** Patch context inspection explicitly indicates when requested lines fall outside the patch, preserving DiffGuard's integrity standard without claiming non-existent repository knowledge.

---

## Conclusion & Readiness
Phase 2.1 is complete. The tool declarations and secure dispatcher are fully tested, backward-compatible, and ready for integration into the agent's multi-turn investigation loop in Phase 2.2.

