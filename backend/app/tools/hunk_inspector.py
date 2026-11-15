"""
Deterministic, read-only implementations for diff and hunk inspection tools.
Operates exclusively on in-memory parsed unified diffs without disk or network access.
"""

from typing import Any, Dict, List, Optional
from app.models.diff_models import ParsedDiff, ParsedFile
from app.parser.location_validator import normalize_repo_path
from app.tools.tool_schemas import InspectDiffHunkArgs, InspectPatchContextArgs

MAX_SNIPPET_CHARS = 8_000
MAX_LINE_RANGE_SPAN = 50


def find_file_in_diff(parsed_diff: ParsedDiff, raw_path: str) -> Optional[ParsedFile]:
    """Finds a file in the parsed diff using strict and boundary-safe suffix matching."""
    norm = normalize_repo_path(raw_path)
    if not norm:
        return None

    # 1. Exact match on normalized target or source path
    for f in parsed_diff.files:
        t_norm = normalize_repo_path(f.target_file)
        s_norm = normalize_repo_path(f.source_file)
        if norm in (t_norm, s_norm):
            return f

    # 2. Slash-boundary suffix matching (e.g. 'auth.py' matches 'services/auth.py')
    for f in parsed_diff.files:
        t_norm = normalize_repo_path(f.target_file)
        s_norm = normalize_repo_path(f.source_file)
        for candidate in (t_norm, s_norm):
            if candidate and (candidate.endswith("/" + norm) or norm.endswith("/" + candidate)):
                return f

    return None


def execute_inspect_diff_hunk(parsed_diff: ParsedDiff, args: InspectDiffHunkArgs) -> Dict[str, Any]:
    """
    Retrieves detailed structural information for a single diff hunk.
    """
    file_obj = find_file_in_diff(parsed_diff, args.file_path)
    if not file_obj:
        return {
            "error_code": "FILE_NOT_FOUND",
            "error_message": f"File '{args.file_path}' was not found in the submitted patch."
        }

    total_hunks = len(file_obj.hunks)
    if args.hunk_index >= total_hunks:
        return {
            "error_code": "INVALID_HUNK_INDEX",
            "error_message": f"Hunk index {args.hunk_index} is out of range. File '{file_obj.target_file}' contains {total_hunks} hunk(s)."
        }

    hunk = file_obj.hunks[args.hunk_index]
    canonical_path = normalize_repo_path(file_obj.target_file) or normalize_repo_path(file_obj.source_file)

    context_lines = [line.value for line in hunk.lines if line.line_type == " "]
    raw_hunk_text = hunk.raw_hunk
    truncated = False
    if len(raw_hunk_text) > MAX_SNIPPET_CHARS:
        raw_hunk_text = raw_hunk_text[:MAX_SNIPPET_CHARS] + "\n... [truncated]"
        truncated = True

    return {
        "canonical_file_path": canonical_path,
        "hunk_index": hunk.hunk_index,
        "total_hunks": total_hunks,
        "header": hunk.header,
        "source_start": hunk.source_start,
        "source_length": hunk.source_length,
        "target_start": hunk.target_start,
        "target_length": hunk.target_length,
        "added_lines_count": len(hunk.added_lines),
        "deleted_lines_count": len(hunk.deleted_lines),
        "added_lines": hunk.added_lines[:100],
        "deleted_lines": hunk.deleted_lines[:100],
        "context_lines": context_lines[:100],
        "raw_hunk": raw_hunk_text,
        "truncated": truncated
    }


def execute_inspect_patch_context(parsed_diff: ParsedDiff, args: InspectPatchContextArgs) -> Dict[str, Any]:
    """
    Extracts line context available directly within the submitted patch.
    Clarifies limitations when requested lines are outside patch hunks.
    """
    file_obj = find_file_in_diff(parsed_diff, args.file_path)
    if not file_obj:
        return {
            "error_code": "FILE_NOT_FOUND",
            "error_message": f"File '{args.file_path}' was not found in the submitted patch."
        }

    canonical_path = normalize_repo_path(file_obj.target_file) or normalize_repo_path(file_obj.source_file)
    start_line = args.start_line
    end_line = args.end_line if args.end_line is not None else start_line

    if end_line < start_line:
        return {
            "error_code": "INVALID_LINE_RANGE",
            "error_message": f"end_line ({end_line}) cannot be less than start_line ({start_line})."
        }

    range_clamped = False
    if end_line - start_line > MAX_LINE_RANGE_SPAN:
        end_line = start_line + MAX_LINE_RANGE_SPAN
        range_clamped = True

    matched_lines: List[Dict[str, Any]] = []

    for hunk in file_obj.hunks:
        for line in hunk.lines:
            matches = False
            line_no = None

            if args.line_side == "new" and line.target_line_no is not None:
                if start_line <= line.target_line_no <= end_line:
                    matches = True
                    line_no = line.target_line_no
            elif args.line_side == "old" and line.source_line_no is not None:
                if start_line <= line.source_line_no <= end_line:
                    matches = True
                    line_no = line.source_line_no
            elif args.line_side == "both":
                if (line.target_line_no is not None and start_line <= line.target_line_no <= end_line) or \
                   (line.source_line_no is not None and start_line <= line.source_line_no <= end_line):
                    matches = True
                    line_no = line.target_line_no or line.source_line_no

            if matches:
                matched_lines.append({
                    "line_number": line_no,
                    "type": line.line_type,
                    "content": line.value
                })

    if not matched_lines:
        return {
            "canonical_file_path": canonical_path,
            "requested_range": {
                "start_line": start_line,
                "end_line": end_line,
                "line_side": args.line_side
            },
            "available_in_patch": False,
            "lines_found": 0,
            "lines": [],
            "limitation": (
                f"Lines {start_line}-{end_line} on side '{args.line_side}' for '{canonical_path}' "
                "fall outside all patch hunks. Full file content is unavailable without a cloned repository."
            )
        }

    return {
        "canonical_file_path": canonical_path,
        "requested_range": {
            "start_line": start_line,
            "end_line": end_line,
            "line_side": args.line_side
        },
        "available_in_patch": True,
        "lines_found": len(matched_lines),
        "lines": matched_lines,
        "range_clamped": range_clamped
    }

