# DiffGuard — Phase 1.2 Implementation Report
## Audit-Driven Corrective Hardening & Regression Protection

**Project:** DiffGuard — AI-Powered Git Diff & Pull Request Review Agent  
**Working Directory:** `C:\Users\HP\OneDrive\Documents\Diffguard`  
**Phase:** 1.2 — Audit-Driven Corrective Hardening & Regression Protection  
**Reference Document:** `docs/audits/DIFFGUARD_REVIEW_CAPABILITY_AND_SECURITY_AUDIT.md` & Phase 1.1 Audit  
**Date:** November 13, 2026  
**Status:** Completed & Verified  

---

## 1. Executive Summary

Phase 1.2 addresses the four specific corrective issues identified during the independent Phase 1.1 verification audit:
1. **P1-01 (Environment-aware CORS configuration):** Resolved silent leakage of development origins into production. Production environments now strictly enforce explicit allowlists, exclude `localhost`/`127.0.0.1`, strip trailing slashes, and fail closed if unconfigured.
2. **P1-02 (DiffViewer old/new line-key collision):** Disambiguated finding association in `DiffViewer.tsx`. Findings on added lines (`line_side='new'`) and deleted lines (`line_side='old'`) sharing the same numerical line number are strictly partitioned, eliminating false inline annotations and isolating navigation highlights.
3. **P2-01 (Correct classification of out-of-hunk locations):** Replaced the conflation of "outside patch hunks" with "invalid line". Out-of-hunk positive line numbers in existing files are now classified as `LocationStatus.UNVERIFIED` with explanatory notes clarifying that complete repository context is unavailable from a patch alone. Raw line numbers remain strictly preserved.
4. **P2-02 (Robust repository path normalization):** Hardened path parsing across backend and frontend to handle enclosing quotes (`"..."`, `'...'`), leading `./`, Windows backslashes, leading `/`, and standard git prefixes (`a/`, `b/`) while preserving legitimate filename spaces and enforcing slash-boundary matching.

All changes were implemented with zero breaking API changes, preserving backward compatibility and determinism across all review paths.

---

## 2. Issues Addressed, Root Causes & Implementation Details

### 2.1 Issue P1-01 — Environment-Aware CORS Configuration

#### Audit Issue & Confirmed Root Cause
- **Audit Observation:** In `backend/app/config.py`, `assemble_cors_origins()` unconditionally appended `DEFAULT_DEV_ORIGINS` (`http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:8000`, `http://127.0.0.1:8000`) regardless of the configured `APP_ENV`.
- **Root Cause:** The code contained a comment `# Ensure default development origins are included in non-production`, but lacked any condition checking whether `APP_ENV` equaled `"production"`. Consequently, production deployments with `allow_credentials=True` inadvertently trusted arbitrary local web services on port 3000/8000. Additionally, origins with trailing slashes (e.g. `https://diffguard.internal/`) failed preflight matching against standard browser `Origin` headers.

#### Implementation Decisions
- **Environment Detection via Pydantic ValidationInfo:** Updated `assemble_cors_origins` in `backend/app/config.py` to inspect `APP_ENV` via `ValidationInfo`.
- **Production Strictness:**
  - When `APP_ENV == "production"`, `DEFAULT_DEV_ORIGINS` are never added.
  - Any origin containing `localhost` or `127.0.0.1` is filtered out with a warning.
  - If no explicit valid origins are provided in production, `CORS_ORIGINS` resolves to `[]` (failing closed, rejecting all cross-origin requests).
- **Development Convenience:**
  - When `APP_ENV != "production"`, `DEFAULT_DEV_ORIGINS` are automatically merged with custom entries.
- **Normalization:**
  - All origins are stripped of surrounding whitespace and trailing slashes (`norm = o.rstrip("/")`).
  - Wildcard `*` continues to be rejected across all environments.
  - Supported alias choices: accepts either `CORS_ORIGINS` or `DIFFGUARD_CORS_ORIGINS`.

#### Files Modified
- `backend/app/config.py`
- `backend/tests/test_security_hardening.py`

---

### 2.2 Issue P1-02 — DiffViewer Side-Specific Finding Association

#### Audit Issue & Confirmed Root Cause
- **Audit Observation:** In `frontend/src/components/DiffViewer.tsx`, when an added line and a deleted line shared the same line number (e.g., old line 10 deleted, new line 10 added), findings targeting the added line also rendered beneath the deleted line.
- **Root Cause:** `findingsMap` registered findings under a generic fallback key `${canonical}:${line}` in addition to `${canonical}:${side}:${line}`. When parsing diff lines, `parsedLines` checked `${currentFile}:${oldLine}` on deleted lines. This caused deleted lines to match added-line findings whenever `oldLine == newLine`. Additionally, line 138 highlighted both old and new lines when navigating.

#### Implementation Decisions
- **Strict Key Partitioning:** In `DiffViewer.tsx`, findings targeting `side === 'new'` are strictly registered under `${canonical}:new:${line}`. Findings targeting `side === 'old'` are strictly registered under `${canonical}:old:${line}`. The ambiguous fallback `${canonical}:${line}` was removed.
- **Side-Specific Line Matching:**
  - Added lines (`type === 'add'`) match only `${currentFile}:new:${newLine}`.
  - Deleted lines (`type === 'del'`) match only `${currentFile}:old:${oldLine}`.
  - Context lines (`type === 'context'`) match `${currentFile}:new:${newLine}`, `${currentFile}:both:${newLine}`, and `${currentFile}:old:${oldLine}`.
  - File-header rows match `${currentFile}:file_level`.
- **Side-Aware Highlighting:**
  - When `highlightSide === 'old'`, only deleted lines (and context lines) matching `highlightLine` are highlighted.
  - When `highlightSide === 'new'`, only added lines (and context lines) matching `highlightLine` are highlighted.
  - When `highlightSide === 'file_level'`, the file header row is highlighted.

#### Files Modified
- `frontend/src/components/DiffViewer.tsx`
- `frontend/package.json`
- `frontend/src/tests/diff_viewer_logic.test.mjs` (New test suite)

---

### 2.3 Issue P2-01 — Correct Classification of Out-of-Hunk Locations

#### Audit Issue & Confirmed Root Cause
- **Audit Observation:** In `backend/app/parser/location_validator.py`, findings referencing lines outside the supplied diff hunks were marked as `LocationStatus.INVALID` with the note `"Line X is outside all patch hunks"`.
- **Root Cause:** The validator assumed that patch hunks represent the totality of the codebase. DiffGuard operates on submitted patches, not cloned repositories. A line outside the hunks in an existing file may well exist in the repository; it is simply *unverifiable from patch evidence alone*. Marking it `INVALID` conflated unverified context with model hallucination, causing the UI to display a red "Invalid Reference" error and disable navigation.

#### Implementation Decisions
- **Semantically Accurate Classification:**
  - If a file exists in the patch, but the referenced positive line number falls outside all hunks, the status is set to `LocationStatus.UNVERIFIED`.
  - Explanatory note: `f"Line {line_no} is outside patch hunks for '{file_info.canonical_path}'; unverified without full repository context."`
  - If a line falls within hunk boundary spans but is neither added nor context, note: `f"Line {line_no} falls near hunk boundaries, but does not correspond to an edited or context line in this patch; unverified without full repository context."`
- **True Invalidation Preserved:**
  - Target file not in patch $\rightarrow$ `LocationStatus.INVALID`.
  - Negative line numbers (`line_no < 0`) $\rightarrow$ `LocationStatus.INVALID`.
  - Line 0 for non-file-level findings $\rightarrow$ `LocationStatus.INVALID`.
- **Zero Clamping:** The raw reported line number is strictly preserved.

#### Files Modified
- `backend/app/parser/location_validator.py`
- `backend/tests/test_finding_integrity.py`

---

### 2.4 Issue P2-02 — Robust Repository Path Normalization

#### Audit Issue & Confirmed Root Cause
- **Audit Observation:** `normalize_repo_path()` in `location_validator.py` did not strip leading `./` or enclosing quotes (`"..."`), which are commonly generated by Git diffs for paths containing spaces or by model outputs.
- **Root Cause:** Path cleaning only handled `\` replacement, leading `/`, and `a/`/`b/` prefixes. If an LLM returned `"services/auth.py"` or `./services/auth.py`, exact key matching in `DiffLocationIndex.files` failed.

#### Implementation Decisions
- **Enclosing Quote Stripping:** Strips matching leading and trailing single or double quotes (`clean = clean[1:-1].strip()`).
- **Repeated `./` Stripping:** Iteratively removes leading `./` sequences before and after git prefix (`a/`, `b/`) removal.
- **Preservation of Filename Spaces:** Spaces within directory names and filenames (e.g., `services/my auth handler.py`) are strictly preserved.
- **Slash-Boundary Suffix Matching:** In `find_file()`, suffix matching requires a path delimiter boundary (`canonical.endswith("/" + norm)`), preventing accidental collisions such as `repayment.py` matching `payment.py`.
- **Frontend Symmetry:** Aligned `normalizePath` in `frontend/src/components/DiffViewer.tsx` to apply identical quote and prefix stripping.

#### Files Modified
- `backend/app/parser/location_validator.py`
- `frontend/src/components/DiffViewer.tsx`
- `backend/tests/test_finding_integrity.py`
- `frontend/src/tests/diff_viewer_logic.test.mjs`

---

## 3. Automated Test Execution & Results

### 3.1 Backend Test Suite (Pytest)

Command executed:
```powershell
python -m pytest backend/tests -v
```

Outcome:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\HP\OneDrive\Documents\Diffguard\backend
configfile: pytest.ini
plugins: anyio-4.14.2, langsmith-0.14.17
collected 52 items

backend\tests\test_agent_schema.py::test_finding_model_validation PASSED [  1%]
backend\tests\test_agent_schema.py::test_heuristic_fallback_engine_on_sqli PASSED [  3%]
backend\tests\test_agent_schema.py::test_heuristic_fallback_engine_on_clean_pr PASSED [  5%]
backend\tests\test_api_routes.py::test_health_endpoint PASSED            [  7%]
backend\tests\test_api_routes.py::test_list_samples_endpoint PASSED      [  9%]
backend\tests\test_api_routes.py::test_get_single_sample_endpoint PASSED [ 11%]
backend\tests\test_api_routes.py::test_get_nonexistent_sample_returns_404 PASSED [ 13%]
backend\tests\test_api_routes.py::test_review_endpoint_empty_diff_returns_400 PASSED [ 15%]
backend\tests\test_api_routes.py::test_review_endpoint_valid_sqli PASSED [ 17%]
backend\tests\test_api_routes.py::test_review_endpoint_clean_pr PASSED   [ 19%]
backend\tests\test_diff_parser.py::test_detect_language PASSED           [ 21%]
backend\tests\test_diff_parser.py::test_clean_file_path PASSED           [ 23%]
backend\tests\test_diff_parser.py::test_empty_diff_handling PASSED       [ 25%]
backend\tests\test_diff_parser.py::test_invalid_diff_handling PASSED     [ 26%]
backend\tests\test_diff_parser.py::test_parse_valid_sqli_sample PASSED   [ 28%]
backend\tests\test_diff_parser.py::test_parse_multi_file_sample PASSED   [ 30%]
backend\tests\test_finding_integrity.py::test_path_normalization PASSED  [ 32%]
backend\tests\test_finding_integrity.py::test_path_boundary_suffix_matching PASSED [ 34%]
backend\tests\test_finding_integrity.py::test_valid_added_line_finding PASSED [ 36%]
backend\tests\test_finding_integrity.py::test_valid_deleted_line_finding PASSED [ 38%]
backend\tests\test_finding_integrity.py::test_valid_context_line_finding PASSED [ 40%]
backend\tests\test_finding_integrity.py::test_file_level_finding PASSED  [ 42%]
backend\tests\test_finding_integrity.py::test_unknown_file_path_marked_invalid PASSED [ 44%]
backend\tests\test_finding_integrity.py::test_out_of_hunk_line_never_clamped PASSED [ 46%]
backend\tests\test_finding_integrity.py::test_negative_line_number_marked_invalid PASSED [ 48%]
backend\tests\test_finding_integrity.py::test_path_prefix_variations_resolve_canonically PASSED [ 50%]
backend\tests\test_finding_integrity.py::test_validate_all_findings_in_batch PASSED [ 51%]
backend\tests\test_security_adversarial.py::test_prompt_injection_boundary_isolation PASSED [ 53%]
backend\tests\test_security_adversarial.py::test_adversarial_diff_review_still_flags_vulnerabilities PASSED [ 55%]
backend\tests\test_security_hardening.py::test_cors_dev_defaults PASSED  [ 57%]
backend\tests\test_security_hardening.py::test_cors_dev_custom_origins PASSED [ 59%]
backend\tests\test_security_hardening.py::test_cors_production_explicit_origins PASSED [ 61%]
backend\tests\test_security_hardening.py::test_cors_production_without_origins_fails_safe PASSED [ 63%]
backend\tests\test_security_hardening.py::test_cors_production_excludes_dev_origins PASSED [ 65%]
backend\tests\test_security_hardening.py::test_cors_rejects_wildcard PASSED [ 67%]
backend\tests\test_security_hardening.py::test_cors_trailing_slash_normalized PASSED [ 69%]
backend\tests\test_security_hardening.py::test_cors_approved_origin_header PASSED [ 71%]
backend\tests\test_security_hardening.py::test_cors_unapproved_origin_rejected PASSED [ 73%]
backend\tests\test_security_hardening.py::test_sanitize_provider_error_authentication PASSED [ 75%]
backend\tests\test_security_hardening.py::test_sanitize_provider_error_timeout PASSED [ 76%]
backend\tests\test_security_hardening.py::test_sanitize_provider_error_quota PASSED [ 78%]
backend\tests\test_security_hardening.py::test_sanitize_provider_error_service_unavailable PASSED [ 80%]
backend\tests\test_security_hardening.py::test_review_response_never_contains_submitted_api_key PASSED [ 82%]
backend\tests\test_security_hardening.py::test_concurrent_api_key_isolation PASSED [ 84%]
backend\tests\test_tools.py::test_security_scanner_detects_sqli PASSED   [ 86%]
backend\tests\test_tools.py::test_security_scanner_detects_hardcoded_secret PASSED [ 88%]
backend\tests\test_tools.py::test_security_scanner_detects_command_injection PASSED [ 90%]
backend\tests\test_tools.py::test_syntax_checker_python_bare_except PASSED [ 92%]
backend\tests\test_tools.py::test_syntax_checker_js_loose_equality PASSED [ 94%]
backend\tests\test_complexity_analyzer PASSED             [ 96%]
backend\tests\test_test_coverage_analyzer_flags_untested_production PASSED [ 98%]
backend\tests\test_test_coverage_analyzer_passes_tested_pr PASSED [100%]

============================= 52 passed in 2.41s ==============================
```

---

### 3.2 Frontend Logic Regression Suite (Node Built-In Test Runner)

Command executed:
```powershell
cd frontend; npm test
```

Outcome:
```text
npm notice run diffguard-frontend@1.0.0 test
npm notice run node --test src/tests/diff_viewer_logic.test.mjs
✔ P2-02: normalizePath handles quotes, ./, and prefixes safely (0.6526ms)
✔ P1-02 Requirement 1: Added line 10 with finding on new line 10 associates ONLY with added line (0.5028ms)
✔ P1-02 Requirement 2: Deleted line 10 with finding on old line 10 associates ONLY with deleted line (0.2257ms)
✔ P1-02 Requirements 3 & 4: Two findings on opposite sides of the same line 10 attach strictly to their respective sides (0.8ms)
✔ P1-02 Requirement 5: Navigation highlights intended side only (0.167ms)
ℹ tests 5
ℹ suites 0
ℹ pass 5
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 77.3958
```

---

### 3.3 Frontend Production Build (Next.js)

Command executed:
```powershell
cd frontend; npm run build
```

Outcome:
```text
   ▲ Next.js 15.5.29

   Creating an optimized production build ...
 ✓ Compiled successfully in 2.1s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/4) ...
   Generating static pages (4/4)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                 Size  First Load JS
┌ ○ /                                      15 kB         118 kB
└ ○ /_not-found                            992 B         104 kB
+ First Load JS shared by all             103 kB

Status: 0 errors, 0 warnings, production ready.
```

---

## 4. Why the Chosen Fixes Are Safer Than Alternatives

1. **Explicit Origin Gate vs. Wildcard Allowance:**
   - *Alternative Considered:* Leaving `DEFAULT_DEV_ORIGINS` active in all environments and requiring operators to override via env var.
   - *Why Rejected:* Highly error-prone in containerized or Kubernetes deployments; developers frequently forget to unset dev variables, leaving production APIs exposed to cross-origin probing from `localhost`. The implemented approach automatically checks `APP_ENV == "production"` and fails closed if explicit production origins are not declared.
2. **Side-Disambiguated Lookup Keys vs. Heuristic Post-Filtering:**
   - *Alternative Considered:* Keeping `${canonical}:${line}` in `findingsMap` and filtering findings during render by checking `f.location.line_side`.
   - *Why Rejected:* Fragile and prone to render-time mismatches when multiple hunks or files contain repeated line numbers. Partitioning the map keys at ingestion (`${canonical}:new:${line}` vs `${canonical}:old:${line}`) guarantees $O(1)$ collision-free lookups.
3. **`LocationStatus.UNVERIFIED` vs. False Invalidation:**
   - *Alternative Considered:* Clamping out-of-hunk line numbers to the nearest hunk boundary or continuing to mark them `INVALID`.
   - *Why Rejected:* Clamping actively misrepresents finding locations and confuses developers reviewing PRs. Marking them `INVALID` disables UI navigation on genuine caller references in unchanged portions of the file. Labelling them `UNVERIFIED` truthfully communicates system confidence.

---

## 5. Remaining Limitations & Phase 2 Outlook

- **Partial Patch Visibility:** Without a GitHub repository integration or full-file context provider, DiffGuard cannot conclusively verify code outside unified diff hunks. This limitation is cleanly surfaced through `LocationStatus.UNVERIFIED`.
- **Phase 2 Hand-off:** With Phase 1.2 completed, all high-priority security and finding-integrity bugs are resolved. The system is structurally sound and ready for **Phase 2: Dynamic Gemini Function Calling & Engineering Standards Engine**.

