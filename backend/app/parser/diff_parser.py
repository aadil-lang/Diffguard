"""
Robust Git Diff and Unified Patch Parser.
Uses unidiff with automated header correction, fallback parsing, and language detection.
"""

import os
import re
from typing import List, Optional
from unidiff import PatchSet, UnidiffParseError
from app.models.diff_models import ParsedDiff, ParsedFile, ParsedHunk, ParsedLine
from app.config import settings


EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
}


def detect_language(file_path: str) -> str:
    """Infer programming language from file extension."""
    if not file_path:
        return "unknown"
    _, ext = os.path.splitext(file_path.lower())
    return EXTENSION_LANGUAGE_MAP.get(ext, "unknown")


def clean_file_path(path: str) -> str:
    """Normalize file paths by stripping Git prefixes (a/, b/)."""
    if not path:
        return ""
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def normalize_diff_hunk_headers(diff_text: str) -> str:
    """
    Recalculates and standardizes hunk header line counts (@@ -s,len +t,len @@).
    Ensures unidiff strictly succeeds even when diff lines are trimmed or edited.
    """
    lines = diff_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@(.*)$", line)
        if match:
            s_start, t_start, tail = match.group(1), match.group(2), match.group(3)
            j = i + 1
            s_count = 0
            t_count = 0
            hunk_body = []
            while j < len(lines):
                hl = lines[j]
                if hl.startswith("diff --git") or hl.startswith("--- ") or re.match(r"^@@\s+-\d+", hl):
                    break
                if hl.startswith("-"):
                    s_count += 1
                    hunk_body.append(hl)
                elif hl.startswith("+"):
                    t_count += 1
                    hunk_body.append(hl)
                elif hl.startswith(" ") or hl == "":
                    clean_hl = " " + hl if hl and not hl.startswith(" ") else (" " if not hl else hl)
                    s_count += 1
                    t_count += 1
                    hunk_body.append(clean_hl)
                elif hl.startswith("\\ No newline"):
                    hunk_body.append(hl)
                else:
                    clean_hl = " " + hl
                    s_count += 1
                    t_count += 1
                    hunk_body.append(clean_hl)
                j += 1
            output_lines.append(f"@@ -{s_start},{s_count} +{t_start},{t_count} @@{tail}")
            output_lines.extend(hunk_body)
            i = j
        else:
            output_lines.append(line)
            i += 1
    return "\n".join(output_lines)


def parse_git_diff(raw_diff: str) -> ParsedDiff:
    """
    Parse unified git diff or patch text into structured ParsedDiff model.
    Handles corrupt diffs, empty input, and binary files with automatic header healing.
    """
    if not raw_diff or not raw_diff.strip():
        return ParsedDiff(
            is_valid=False,
            error_message="The submitted diff is empty. Please provide a valid unified diff or patch.",
            raw_diff=raw_diff or ""
        )

    # Size check
    diff_bytes = len(raw_diff.encode("utf-8"))
    if diff_bytes > settings.MAX_DIFF_SIZE_BYTES:
        return ParsedDiff(
            is_valid=False,
            error_message=f"Diff size ({diff_bytes:,} bytes) exceeds maximum allowable limit of {settings.MAX_DIFF_SIZE_BYTES:,} bytes.",
            raw_diff=raw_diff
        )

    # 1. First attempt: normalise hunk headers and parse with unidiff
    normalized_diff = normalize_diff_hunk_headers(raw_diff)

    patch_set = None
    try:
        patch_set = PatchSet.from_string(normalized_diff)
    except Exception as e:
        # Fallback: try raw diff directly
        try:
            patch_set = PatchSet.from_string(raw_diff)
        except Exception:
            return ParsedDiff(
                is_valid=False,
                error_message=f"Failed to parse unified diff format: {str(e)}",
                raw_diff=raw_diff
            )

    if not patch_set:
        return ParsedDiff(
            is_valid=False,
            error_message="No patched files detected in the provided input. Ensure it starts with standard unified diff headers ('diff --git' or '--- / +++').",
            raw_diff=raw_diff
        )

    parsed_files = []
    total_additions = 0
    total_deletions = 0

    for idx, patched_file in enumerate(patch_set):
        if idx >= settings.MAX_FILES_PER_DIFF:
            break

        source_path = clean_file_path(patched_file.source_file)
        target_path = clean_file_path(patched_file.target_file)
        effective_path = target_path if target_path and target_path != "/dev/null" else source_path

        lang = detect_language(effective_path)

        file_additions = patched_file.added
        file_deletions = patched_file.removed
        total_additions += file_additions
        total_deletions += file_deletions

        hunks_list = []
        for hunk_idx, hunk in enumerate(patched_file):
            parsed_lines = []
            added_lines = []
            deleted_lines = []
            raw_hunk_lines = []

            for line in hunk:
                line_val = line.value.rstrip("\n")
                line_type = line.line_type
                
                parsed_lines.append(
                    ParsedLine(
                        line_type=line_type,
                        source_line_no=line.source_line_no,
                        target_line_no=line.target_line_no,
                        value=line_val
                    )
                )

                if line.is_added:
                    added_lines.append(line_val)
                    raw_hunk_lines.append(f"+{line_val}")
                elif line.is_removed:
                    deleted_lines.append(line_val)
                    raw_hunk_lines.append(f"-{line_val}")
                else:
                    raw_hunk_lines.append(f" {line_val}")

            hunk_obj = ParsedHunk(
                hunk_index=hunk_idx,
                header=str(hunk.section_header or f"@@ -{hunk.source_start},{hunk.source_length} +{hunk.target_start},{hunk.target_length} @@"),
                source_start=hunk.source_start,
                source_length=hunk.source_length,
                target_start=hunk.target_start,
                target_length=hunk.target_length,
                lines=parsed_lines,
                added_lines=added_lines,
                deleted_lines=deleted_lines,
                raw_hunk="\n".join(raw_hunk_lines)
            )
            hunks_list.append(hunk_obj)

        parsed_file_obj = ParsedFile(
            file_index=idx,
            source_file=source_path,
            target_file=target_path,
            is_new_file=getattr(patched_file, "is_added_file", False),
            is_deleted_file=getattr(patched_file, "is_removed_file", False),
            is_binary=getattr(patched_file, "is_binary_file", False),
            language=lang,
            additions=file_additions,
            deletions=file_deletions,
            hunks=hunks_list
        )
        parsed_files.append(parsed_file_obj)

    return ParsedDiff(
        is_valid=True,
        error_message=None,
        files=parsed_files,
        total_files=len(parsed_files),
        total_additions=total_additions,
        total_deletions=total_deletions,
        raw_diff=raw_diff
    )
