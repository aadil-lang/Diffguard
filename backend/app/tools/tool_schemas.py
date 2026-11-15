"""
Strict Pydantic schemas for Gemini tool arguments and standard result envelopes.
"""

from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    """Consistent, JSON-serializable envelope for all tool execution outputs."""
    model_config = ConfigDict(extra="forbid")

    success: bool = Field(..., description="Whether the tool execution succeeded without errors")
    tool_name: str = Field(..., description="The name of the tool that was executed")
    result: Optional[Dict[str, Any]] = Field(None, description="Structured execution payload if successful")
    error_code: Optional[str] = Field(None, description="Standard error code if execution failed")
    error_message: Optional[str] = Field(None, description="Sanitized, human-readable error description")
    cached: bool = Field(False, description="Whether this result was served from the deduplication cache")


class InspectDiffHunkArgs(BaseModel):
    """Arguments for inspect_diff_hunk."""
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(..., min_length=1, description="Relative repository file path to inspect")
    hunk_index: int = Field(0, ge=0, description="Zero-based index of the hunk within the specified file")


class InspectPatchContextArgs(BaseModel):
    """Arguments for inspect_patch_context."""
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(..., min_length=1, description="Relative repository file path to inspect")
    start_line: int = Field(..., ge=1, description="Starting 1-based line number to inspect")
    end_line: Optional[int] = Field(None, ge=1, description="Ending 1-based line number (inclusive)")
    line_side: Literal["new", "old", "both"] = Field("new", description="Diff side: 'new' (target), 'old' (source), or 'both'")

