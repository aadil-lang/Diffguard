"""
Deterministic Location Validator and Line Indexer.
Validates model-generated and heuristic finding locations against the submitted diff structure.
Enforces that model references are never hallucinated or silently clamped.
"""

import os
from typing import Dict, List, Optional, Set, Tuple
from app.models.schemas import Finding, CodeLocation, LocationStatus, LineSide, FindingCategory
from app.models.diff_models import ParsedDiff, ParsedFile


def normalize_repo_path(raw_path: str) -> str:
    """
    Normalizes a file path for consistent matching across diff headers,
    OS path separators, leading prefixes, enclosing quotes, and model responses.
    Preserves internal spaces in filenames.
    """
    if not raw_path:
        return ""
    clean = raw_path.strip()
    # Strip enclosing quotes from diff headers or model responses
    if (clean.startswith('"') and clean.endswith('"')) or (clean.startswith("'") and clean.endswith("'")):
        clean = clean[1:-1].strip()
    # Standardize backslashes to forward slashes
    clean = clean.replace("\\", "/").strip()
    # Strip leading slashes
    clean = clean.lstrip("/")
    # Strip leading ./
    while clean.startswith("./"):
        clean = clean[2:]
    clean = clean.lstrip("/")
    # Strip standard git prefixes (a/, b/)
    if clean.startswith("a/") or clean.startswith("b/"):
        clean = clean[2:]
    while clean.startswith("./"):
        clean = clean[2:]
    return clean.lstrip("/")


class FileLineIndex:
    """Indexes valid old-side, new-side, and hunk line numbers for a single patched file."""

    def __init__(self, canonical_path: str, parsed_file: ParsedFile):
        self.canonical_path = canonical_path
        self.parsed_file = parsed_file
        
        # Line number mappings: line_no -> line_type ('+', '-', ' ')
        self.new_lines: Dict[int, str] = {}
        self.old_lines: Dict[int, str] = {}
        
        # Hunk boundary spans: list of (source_start, source_end, target_start, target_end)
        self.hunk_spans: List[Tuple[int, int, int, int]] = []
        
        self._build_index()

    def _build_index(self):
        for hunk in self.parsed_file.hunks:
            src_start = hunk.source_start
            src_end = src_start + max(0, hunk.source_length)
            tgt_start = hunk.target_start
            tgt_end = tgt_start + max(0, hunk.target_length)
            self.hunk_spans.append((src_start, src_end, tgt_start, tgt_end))

            for line in hunk.lines:
                if line.target_line_no is not None:
                    self.new_lines[line.target_line_no] = line.line_type
                if line.source_line_no is not None:
                    self.old_lines[line.source_line_no] = line.line_type


class DiffLocationIndex:
    """Index mapping normalized file paths to their respective line indices."""

    def __init__(self, parsed_diff: ParsedDiff):
        self.parsed_diff = parsed_diff
        self.files: Dict[str, FileLineIndex] = {}
        self._build()

    def _build(self):
        for f in self.parsed_diff.files:
            target_norm = normalize_repo_path(f.target_file)
            source_norm = normalize_repo_path(f.source_file)
            
            canonical = target_norm if target_norm and target_norm != "dev/null" else source_norm
            file_index = FileLineIndex(canonical, f)
            
            if canonical:
                self.files[canonical] = file_index
            if target_norm and target_norm not in self.files:
                self.files[target_norm] = file_index
            if source_norm and source_norm not in self.files:
                self.files[source_norm] = file_index

    def find_file(self, raw_path: str) -> Optional[FileLineIndex]:
        norm = normalize_repo_path(raw_path)
        if norm in self.files:
            return self.files[norm]
        
        # Suffix matching with boundary check:
        # e.g. 'auth.py' matching 'services/auth.py'
        # Ensures 'payment.py' does not falsely match 'repayment.py'
        for canonical, file_idx in self.files.items():
            if canonical == norm:
                return file_idx
            if canonical.endswith("/" + norm):
                return file_idx
            if norm.endswith("/" + canonical):
                return file_idx
        return None


def validate_finding_location(finding: Finding, location_index: DiffLocationIndex) -> Finding:
    """
    Validates a single finding against the diff location index.
    Updates location_status, line_side, and validation_note without modifying substantive content.
    NEVER silently clamps invalid or unverified line numbers.
    """
    raw_path = finding.location.file_path
    file_info = location_index.find_file(raw_path)

    # 1. Check if file exists in diff
    if not file_info:
        finding.location.location_status = LocationStatus.INVALID
        finding.location.line_side = LineSide.NEW
        finding.location.validation_note = f"File '{raw_path}' was not found in the submitted patch."
        return finding

    # Canonicalize the file path
    finding.location.file_path = file_info.canonical_path
    line_no = finding.location.start_line

    # 2. Check for negative line numbers (impossible coordinates)
    if line_no < 0:
        finding.location.location_status = LocationStatus.INVALID
        finding.location.validation_note = f"Line number {line_no} is negative and invalid."
        return finding

    # 3. Check for File-Level scope (line <= 0, or line == 1 on missing tests / file-level maintainability where line 1 is not in patch)
    is_file_level_category = finding.category in (FindingCategory.MISSING_TEST_COVERAGE, FindingCategory.CODE_QUALITY_AND_MAINTAINABILITY)
    if line_no == 0 or (line_no == 1 and is_file_level_category and line_no not in file_info.new_lines):
        finding.location.location_status = LocationStatus.FILE_LEVEL
        finding.location.line_side = LineSide.FILE_LEVEL
        finding.location.validation_note = "Finding applies to the file as a whole rather than a specific line."
        return finding

    # 4. Check claimed or existing side
    claimed_side = finding.location.line_side

    if claimed_side == LineSide.OLD:
        # Check old-side first for deleted-line references
        if line_no in file_info.old_lines:
            line_type = file_info.old_lines[line_no]
            finding.location.location_status = LocationStatus.VERIFIED
            finding.location.line_side = LineSide.OLD if line_type == "-" else LineSide.BOTH
            finding.location.validation_note = (
                f"Verified on deleted line {line_no}." if line_type == "-" else f"Verified on context line {line_no}."
            )
            return finding
        if line_no in file_info.new_lines:
            line_type = file_info.new_lines[line_no]
            finding.location.location_status = LocationStatus.VERIFIED
            finding.location.line_side = LineSide.NEW if line_type == "+" else LineSide.BOTH
            finding.location.validation_note = f"Verified on new-side line {line_no}."
            return finding
    else:
        # Check new-side first for added/modified references
        if line_no in file_info.new_lines:
            line_type = file_info.new_lines[line_no]
            finding.location.location_status = LocationStatus.VERIFIED
            finding.location.line_side = LineSide.NEW if line_type == "+" else LineSide.BOTH
            finding.location.validation_note = (
                f"Verified on added line {line_no}." if line_type == "+" else f"Verified on context line {line_no}."
            )
            return finding
        if line_no in file_info.old_lines:
            line_type = file_info.old_lines[line_no]
            finding.location.location_status = LocationStatus.VERIFIED
            finding.location.line_side = LineSide.OLD if line_type == "-" else LineSide.BOTH
            finding.location.validation_note = f"Verified on deleted line {line_no}."
            return finding

    # 5. Out-of-hunk lines in an existing file
    # DiffGuard receives a patch, not the complete repo. Therefore, a line outside supplied hunks
    # cannot automatically be assumed nonexistent. It is classified as UNVERIFIED, preserving the
    # original reported line number without silent clamping.
    in_any_span = any(
        (src_start <= line_no <= src_end) or (tgt_start <= line_no <= tgt_end)
        for (src_start, src_end, tgt_start, tgt_end) in file_info.hunk_spans
    )

    finding.location.location_status = LocationStatus.UNVERIFIED
    if in_any_span:
        finding.location.validation_note = (
            f"Line {line_no} falls near hunk boundaries, but does not correspond to an edited or context line in this patch; unverified without full repository context."
        )
    else:
        finding.location.validation_note = (
            f"Line {line_no} is outside patch hunks for '{file_info.canonical_path}'; unverified without full repository context."
        )

    # Note: original line_no is strictly preserved; never clamped.
    return finding


def validate_all_findings(findings: List[Finding], parsed_diff: ParsedDiff) -> List[Finding]:
    """
    Validates location integrity for all findings against the parsed diff.
    """
    index = DiffLocationIndex(parsed_diff)
    validated = []
    for f in findings:
        validated.append(validate_finding_location(f, index))
    return validated
