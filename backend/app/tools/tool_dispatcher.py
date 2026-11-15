"""
Secure Tool Dispatcher with request-scoped governance, Pydantic argument validation,
call budget enforcement, and duplicate invocation caching.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import ValidationError
from google.genai import types

from app.models.diff_models import ParsedDiff
from app.tools.tool_schemas import ToolResult, InspectDiffHunkArgs, InspectPatchContextArgs
from app.tools.hunk_inspector import execute_inspect_diff_hunk, execute_inspect_patch_context

logger = logging.getLogger("diffguard.tools.dispatcher")

DEFAULT_MAX_TOOL_CALLS = 6
MAX_OUTPUT_CHARS = 16_000

# Note on Tool Execution Architecture (F-01 Resolution):
# Exposed tools ('inspect_diff_hunk', 'inspect_patch_context') are strictly in-memory,
# deterministic, read-only dictionary lookups over an already-parsed unidiff structure.
# They perform no file I/O, no network I/O, and no recursive operations.
# Their execution duration is sub-millisecond (< 0.1ms) and strictly bounded by
# MAX_OUTPUT_CHARS (16,000), MAX_SNIPPET_CHARS (8,000), and MAX_LINE_RANGE_SPAN (50).
# No artificial thread-pool timeout wrapper is used, preventing leaked background threads.

ALLOWED_TOOLS: Set[str] = {
    "inspect_diff_hunk",
    "inspect_patch_context"
}


class ToolDispatcher:
    """
    Request-scoped dispatcher enforcing tool allowlists, Pydantic argument validation,
    invocation attempt accounting, budget caps, and duplicate call memoization.
    """

    def __init__(self, parsed_diff: ParsedDiff, max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS):
        self.parsed_diff = parsed_diff
        self.max_tool_calls = max_tool_calls
        self._calls_count: int = 0
        self._history: List[Dict[str, Any]] = []
        self._cache: Dict[Tuple[str, str], ToolResult] = {}

    @property
    def calls_count(self) -> int:
        return self._calls_count

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def dispatch(self, tool_name: str, arguments: Optional[Union[Dict[str, Any], str]] = None) -> ToolResult:
        """
        Validates, accounts, and executes a requested tool call.
        Guarantees structured ToolResult response and never raises unhandled exceptions.
        Counts all model-requested tool invocation attempts consistently against the budget.
        """
        # 1. Budget enforcement check
        if self._calls_count >= self.max_tool_calls:
            logger.warning(f"Tool call budget exceeded ({self._calls_count}/{self.max_tool_calls}). Rejecting '{tool_name}'.")
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error_code="BUDGET_EXCEEDED",
                error_message=f"Maximum tool call budget ({self.max_tool_calls} calls) reached. Further tool calls are restricted."
            )

        # Increment attempt counter for this budget slot
        self._calls_count += 1
        call_index = self._calls_count
        t0 = time.time()

        # 2. Normalize and validate arguments dictionary
        raw_args: Dict[str, Any] = {}
        if arguments is None:
            raw_args = {}
        elif isinstance(arguments, str):
            try:
                raw_args = json.loads(arguments) if arguments.strip() else {}
            except Exception as json_err:
                duration_ms = int((time.time() - t0) * 1000)
                res = ToolResult(
                    success=False,
                    tool_name=tool_name,
                    error_code="INVALID_ARGUMENTS",
                    error_message=f"Arguments string could not be parsed as valid JSON: {str(json_err)}"
                )
                self._history.append({
                    "call_index": call_index,
                    "tool_name": tool_name,
                    "arguments": {"raw": arguments},
                    "success": False,
                    "error_code": "INVALID_ARGUMENTS",
                    "duration_ms": duration_ms
                })
                return res
        elif isinstance(arguments, dict):
            raw_args = arguments
        else:
            duration_ms = int((time.time() - t0) * 1000)
            res = ToolResult(
                success=False,
                tool_name=tool_name,
                error_code="INVALID_ARGUMENTS",
                error_message=f"Arguments must be a JSON object, got {type(arguments).__name__}."
            )
            self._history.append({
                "call_index": call_index,
                "tool_name": tool_name,
                "arguments": {"raw_type": type(arguments).__name__},
                "success": False,
                "error_code": "INVALID_ARGUMENTS",
                "duration_ms": duration_ms
            })
            return res

        # 3. Check duplicate invocation cache (memoization)
        cache_key = (tool_name, json.dumps(raw_args, sort_keys=True))
        if cache_key in self._cache:
            duration_ms = int((time.time() - t0) * 1000)
            cached_result = self._cache[cache_key].model_copy()
            cached_result.cached = True
            logger.info(f"Serving tool call '{tool_name}' from deduplication cache.")
            self._history.append({
                "call_index": call_index,
                "tool_name": tool_name,
                "arguments": raw_args,
                "success": cached_result.success,
                "error_code": cached_result.error_code,
                "duration_ms": duration_ms,
                "cached": True
            })
            return cached_result

        # 4. Strict allowlist validation
        if tool_name not in ALLOWED_TOOLS:
            duration_ms = int((time.time() - t0) * 1000)
            logger.warning(f"Rejected unauthorized tool call: '{tool_name}'.")
            res = ToolResult(
                success=False,
                tool_name=tool_name,
                error_code="UNKNOWN_TOOL",
                error_message=f"Tool '{tool_name}' is not recognized or not authorized for execution."
            )
            self._history.append({
                "call_index": call_index,
                "tool_name": tool_name,
                "arguments": raw_args,
                "success": False,
                "error_code": "UNKNOWN_TOOL",
                "duration_ms": duration_ms
            })
            return res

        # 5. Argument validation via Pydantic schemas
        validated_args: Any = None
        try:
            if tool_name == "inspect_diff_hunk":
                validated_args = InspectDiffHunkArgs(**raw_args)
            elif tool_name == "inspect_patch_context":
                validated_args = InspectPatchContextArgs(**raw_args)
        except ValidationError as val_err:
            duration_ms = int((time.time() - t0) * 1000)
            res = ToolResult(
                success=False,
                tool_name=tool_name,
                error_code="INVALID_ARGUMENTS",
                error_message=f"Validation failed for tool arguments: {val_err.errors()}"
            )
            self._history.append({
                "call_index": call_index,
                "tool_name": tool_name,
                "arguments": raw_args,
                "success": False,
                "error_code": "INVALID_ARGUMENTS",
                "duration_ms": duration_ms
            })
            return res

        # 6. Execute deterministic in-memory tool logic
        try:
            if tool_name == "inspect_diff_hunk":
                exec_payload = execute_inspect_diff_hunk(self.parsed_diff, validated_args)
            elif tool_name == "inspect_patch_context":
                exec_payload = execute_inspect_patch_context(self.parsed_diff, validated_args)
            else:
                exec_payload = {"error_code": "UNHANDLED_TOOL", "error_message": "Tool handler not found."}

            duration_ms = int((time.time() - t0) * 1000)

            # Check if domain-level error was returned
            if "error_code" in exec_payload:
                res = ToolResult(
                    success=False,
                    tool_name=tool_name,
                    error_code=exec_payload.get("error_code"),
                    error_message=exec_payload.get("error_message")
                )
            else:
                # Output size limit safeguard
                payload_str = json.dumps(exec_payload)
                if len(payload_str) > MAX_OUTPUT_CHARS:
                    exec_payload = {
                        "canonical_file_path": exec_payload.get("canonical_file_path"),
                        "truncated": True,
                        "warning": "Payload exceeded size threshold; output trimmed for model context window.",
                        "summary": f"{exec_payload.get('lines_found', 0)} lines inspected."
                    }

                res = ToolResult(
                    success=True,
                    tool_name=tool_name,
                    result=exec_payload
                )

        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            logger.exception(f"Unexpected error executing tool '{tool_name}'")
            res = ToolResult(
                success=False,
                tool_name=tool_name,
                error_code="EXECUTION_ERROR",
                error_message="Tool execution encountered an internal error."
            )

        # 7. Record accounting and cache result
        self._history.append({
            "call_index": call_index,
            "tool_name": tool_name,
            "arguments": raw_args,
            "success": res.success,
            "error_code": res.error_code,
            "duration_ms": duration_ms
        })
        self._cache[cache_key] = res
        return res

    def to_function_response_part(self, tool_name: str, result: ToolResult) -> types.Part:
        """Converts a ToolResult into a Google GenAI types.Part for multi-turn function responses."""
        return types.Part.from_function_response(
            name=tool_name,
            response=result.model_dump()
        )

