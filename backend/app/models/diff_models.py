"""
Internal models for parsed git diff representations.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ParsedLine(BaseModel):
    line_type: str  # '+', '-', ' '
    source_line_no: Optional[int] = None
    target_line_no: Optional[int] = None
    value: str


class ParsedHunk(BaseModel):
    hunk_index: int
    header: str
    source_start: int
    source_length: int
    target_start: int
    target_length: int
    lines: List[ParsedLine] = Field(default_factory=list)
    added_lines: List[str] = Field(default_factory=list)
    deleted_lines: List[str] = Field(default_factory=list)
    raw_hunk: str = ""


class ParsedFile(BaseModel):
    file_index: int
    source_file: str
    target_file: str
    is_new_file: bool = False
    is_deleted_file: bool = False
    is_binary: bool = False
    language: str = "unknown"
    additions: int = 0
    deletions: int = 0
    hunks: List[ParsedHunk] = Field(default_factory=list)


class ParsedDiff(BaseModel):
    is_valid: bool = True
    error_message: Optional[str] = None
    files: List[ParsedFile] = Field(default_factory=list)
    total_files: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    raw_diff: str = ""

