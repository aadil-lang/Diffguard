# DiffGuard — Engineering Journal

This engineering journal documents technical decisions, architectural investigations, environment observations, and incident records across DiffGuard development phases.

---

## Entry EJ-2026-11-14-01: Windows Sandbox Socket Restriction ([WinError 10013])
- **Date & Scenario:** 2026-11-14 | Application Environment Startup & API Route Verification
- **Classification:** `ENVIRONMENT_ISSUE`
- **Observed Behavior:**
  Running `uvicorn` server binding or `FastAPI TestClient` in standard sandbox mode on Windows triggers `PermissionError: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions` or hangs during `socket.socketpair()` creation.
- **Expected Behavior:**
  Local loopback connections (127.0.0.1:8000) or in-memory asyncio event loop socket pairs execute without OS socket permission blocks.
- **Reproduction Steps:**
  Execute `python -c "import socket; socket.socketpair()"` inside the standard Windows sandbox.
- **Root Cause:**
  Windows OS sandbox isolation restricts local socket creation and loopback socketpair IPC, which `asyncio` and `httpx` rely on for event loop communication.
- **Investigation Performed:**
  Confirmed that pure AST, unidiff parsing, and heuristic evaluation execute cleanly in sandbox, while commands requiring loopback TCP sockets require sandbox bypass (`BypassSandbox: true`).
- **Resolution or Workaround:**
  All socket-requiring end-to-end integration tests and ASGI probes run with sandbox bypass, while all 148 backend unit tests and static analysis rules remain fully sandboxed.
- **Verification Performed:**
  `backend/tests/test_api_routes.py` and `dogfood_evaluation.py` passed all 7 endpoints in <1s unsandboxed.
- **Remaining Limitation:**
  Live local servers must be started unsandboxed if manual browser access is desired.
- **Relevant Files / Logs:**
  `scratch/dogfood_evaluation.py`, `backend/app/main.py`.

---

## Entry EJ-2026-11-14-02: Hardcoded Secret Regex Boundary False Negative (`JWT_SECRET_KEY`)
- **Date & Scenario:** 2026-11-14 | Scenario A (`sample-sqli-auth`) Evaluation
- **Classification:** `EVALUATION_FINDING`
- **Observed Behavior:**
  In `sample-sqli-auth`, line 16 contains `JWT_SECRET_KEY = "prod_jwt_super_secret_key_diffguard_9876543210"`. While the SQL injection defect (line 24) and missing tests were flagged, the hardcoded secret was not detected by the deterministic scanner in fallback mode.
- **Expected Behavior:**
  The deterministic security scanner should flag high-entropy private keys and credentials assigned to variables containing `SECRET` or `KEY`.
- **Reproduction Steps:**
  Run `scan_security_issues('JWT_SECRET_KEY = "prod_jwt_super_secret_key_diffguard_9876543210"')`.
- **Root Cause:**
  Rule `SEC-SECRET-002` in `backend/app/tools/security_scanner.py` uses pattern `(?i)(api[_-]?key|secret|token|password|jwt[_-]?secret|private[_-]?key)\s*[:=]`. Because the variable is named `JWT_SECRET_KEY`, the word `SECRET` is followed by `_KEY`, failing the `\s*[:=]` lookahead.
- **Investigation Performed:**
  Tested regex against `JWT_SECRET = "..."` (matches) vs `JWT_SECRET_KEY = "..."` (fails). Confirmed failure is purely a regex boundary constraint.
- **Resolution or Workaround:**
  Documented as a known limitation of the deterministic heuristic fallback engine. In live Gemini mode, contextual LLM reasoning flags the secret semantically; in deterministic mode, recommending adding `_key` support in a future corrective update.
- **Verification Performed:**
  Documented in Finding Integrity Scorecard for Scenario A.
- **Remaining Limitation:**
  Variables ending in compound suffixes (e.g. `_SECRET_KEY`, `_API_TOKEN_VALUE`) are not matched by deterministic regex `SEC-SECRET-002`.
- **Relevant Files / Logs:**
  `backend/app/tools/security_scanner.py`, `backend/app/samples/sample_diffs.py`.

---

## Entry EJ-2026-11-14-03: Incomplete Hunk Boundary Handling in Function Length Rule
- **Date & Scenario:** 2026-11-14 | Scenario C (Standards Violations)
- **Classification:** `MODEL_BEHAVIOR`
- **Observed Behavior:**
  When a function spans >50 lines in a diff but the hunk terminates without an unindented line, `evaluate_function_length` does not emit a violation.
- **Expected Behavior:**
  The rule should only emit violations when complete function boundaries are provable from hunk context, avoiding false positives on truncated diffs.
- **Reproduction Steps:**
  Submit a diff where a function is defined at line 1 and the hunk ends at line 55 without an unindented enclosing scope or following function.
- **Root Cause:**
  `backend/app/standards/rules/function_length.py` checks `if not is_complete: continue`. Because diff hunks only show localized changes, the engine intentionally refuses to guess whether the function ended on line 56 or line 500 outside the patch.
- **Investigation Performed:**
  Verified that when an unindented terminating line (e.g., another `def` or `class`) is present in the hunk, the function length violation is reliably emitted.
- **Resolution or Workaround:**
  Confirmed by design: preventing false positives on partial diff hunks is an architectural invariant of the engineering standards engine.
- **Verification Performed:**
  Tested complete vs incomplete hunk boundaries in `scratch/test_complete_func_boundary.py`.
- **Remaining Limitation:**
  Functions that terminate outside the diff hunk boundaries cannot be measured for total length by deterministic hunk analysis alone.
- **Relevant Files / Logs:**
  `backend/app/standards/rules/function_length.py`.

---

## Entry EJ-2026-11-14-04: Documentation Reconciliation in Audit Reports
- **Date & Scenario:** 2026-11-14 | Preliminary Repository & Audit Inspection
- **Classification:** `DOCUMENTATION_ISSUE`
- **Observed Behavior:**
  `DIFFGUARD_PHASE_3_1_6_INDEPENDENT_VERIFICATION_REPORT.md` had an incorrect date ("March 2026"), substituted descriptions for F-01 through F-07 that did not match the original Phase 3.1 audit report, referenced `.diffguard/standards.json` (which is unsupported), and lacked explicit clarification of Pydantic default provenance.
- **Expected Behavior:**
  Audit documentation must reflect actual execution dates, accurately cite historical audit findings, reference `.diffguard.yaml` exclusively, and clarify that omitted `line_side` attributes lack independent new-side provenance.
- **Reproduction Steps:**
  Compare `DIFFGUARD_PHASE_3_1_INDEPENDENT_AUDIT_REPORT.md` with `DIFFGUARD_PHASE_3_1_6_INDEPENDENT_VERIFICATION_REPORT.md`.
- **Root Cause:**
  Drafting discrepancy during Phase 3.1.6 report synthesis.
- **Resolution or Workaround:**
  Updated `docs/audits/DIFFGUARD_PHASE_3_1_6_INDEPENDENT_VERIFICATION_REPORT.md` to November 14, 2026, restored authentic F-01 through F-07 descriptions, replaced JSON references with `.diffguard.yaml`, and clarified Pydantic defaulting.
- **Verification Performed:**
  File inspected and verified cleanly.
- **Remaining Limitation:**
  None.
- **Relevant Files / Logs:**
  `docs/audits/DIFFGUARD_PHASE_3_1_6_INDEPENDENT_VERIFICATION_REPORT.md`.

---

## Entry EJ-2026-11-14-05: Secret Detection Refinement for Compound Credential Names (`JWT_SECRET_KEY`)
- **Date & Scenario:** 2026-11-14 | Phase 3.2.1 Targeted Implementation (Linked to EJ-2026-11-14-02)
- **Classification:** `EVALUATION_FINDING`
- **Problem:**
  Hardcoded credential false negative involving `JWT_SECRET_KEY = "prod_jwt_super_secret_key_diffguard_9876543210"` in `sample-sqli-auth`.
- **Discovery:**
  Phase 3.2 controlled dogfooding (documented in `EJ-2026-11-14-02`).
- **Root Cause:**
  Rule `SEC-SECRET-002` in `backend/app/tools/security_scanner.py` defined its variable name pattern as:
  `(?i)(api[_-]?key|secret|token|password|jwt[_-]?secret|private[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{12,})["']`.
  Because `JWT_SECRET_KEY` has `_KEY` following `SECRET`, the characters `_KEY` failed the `\s*[:=]` lookahead. Furthermore, `key` by itself was not recognized unless preceded by `api` or `private`.
- **Correction:**
  Updated the regex pattern in `backend/app/tools/security_scanner.py` to:
  `(?i)(api[_-]?key|secret(?:[_-]?(?:key|token))?|token|password|passwd|jwt[_-]?secret(?:[_-]?key)?|private[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{12,})["']`.
  This allows compound secret names ending in `_KEY` or `_TOKEN` (such as `JWT_SECRET_KEY`, `AWS_SECRET_KEY`, `SECRET_KEY`, `APP_SECRET_TOKEN`) while strictly maintaining non-credential variable exclusions.
- **Regression Protection:**
  Created `backend/tests/test_secret_detection_refinement_phase321.py` with 19 comprehensive unit and integration tests across 4 categories:
  1. Missed compound secret names (`JWT_SECRET_KEY`, `AWS_SECRET_KEY`, `DATABASE_PASSWORD`, `API_TOKEN`, `PRIVATE_KEY`).
  2. Backward compatibility with previously supported formats (`JWT_SECRET`, `api_key`, `token`, `password`, `SECRET`, `client_secret`).
  3. False positive resistance (`user_key`, `keyboard_layout`, `token_count`, `secret_mode_enabled`, `public_key_name`, `cache_key`, `primary_key`, `sort_key`).
  4. End-to-end evidence, diff-side, line number integrity, and Scenario A (detecting all 3 defects) / Scenario B (clean PR).
  All 167 backend tests pass cleanly.
- **Remaining Limitations:**
  Credentials assigned using dynamic string formatting, multi-line concatenations, or non-standard variable names without credential semantic markers (e.g., `x = "secret_value_1234567890"`) remain unsupported by deterministic regex scanning and rely on contextual LLM analysis.
- **Relevant Files / Logs:**
  `backend/app/tools/security_scanner.py`, `backend/tests/test_secret_detection_refinement_phase321.py`, `docs/audits/DIFFGUARD_PHASE_3_2_1_IMPLEMENTATION_REPORT.md`.

---

## Entry EJ-2026-11-14-06: Secret Evidence Redaction & Disclosure Protection
- **Date & Scenario:** 2026-11-14 | Phase 3.2.4 Security Hardening (Linked to EJ-2026-11-14-02 & EJ-2026-11-14-05)
- **Classification:** `SECURITY_HARDENING`
- **Discovery:**
  During Phase 3.2.3 source inspection, it was observed that when rule `SEC-SECRET-002` matched a hardcoded credential, `clean_line.strip()` was directly assigned to `matched_code`, preserving the raw credential value in finding evidence.
- **Root Cause:**
  `scan_security_issues()` in `backend/app/tools/security_scanner.py` passed the unredacted source line as `matched_code`, which downstream components forwarded into `location.code_context`, structured review outputs, and SSE streaming payloads.
- **Security Impact:**
  Detected hardcoded credentials could be disclosed through generated review findings, JSON API responses, SSE event payloads, and frontend review reports.
- **Correction:**
  Implemented surgical value-level evidence redaction in `scan_security_issues()`: for `SEC-SECRET-002`, the exact span of capturing group 2 (`match.span(2)`) is replaced with `[REDACTED]`, producing evidence of the form `VAR_NAME = "[REDACTED]"` while preserving variable name, assignment syntax, and quotes. Non-secret rules remain completely untouched.
- **Verification:**
  Created `backend/tests/test_secret_evidence_redaction_phase324.py` with 15 tests verifying:
  1. Secret value redaction for single and double quotes.
  2. Compound credential identifiers (`JWT_SECRET_KEY`, `AWS_SECRET_KEY`, `DATABASE_PASSWORD`, `API_TOKEN`, `PRIVATE_KEY`).
  3. Non-secret variables remain untouched and clean.
  4. Finding location and metadata preservation (`rule_id`, `severity`, `file_path`, `line_number`, `line_side`).
  5. Recursive string scanning across full `/api/review` JSON responses.
  6. Recursive string scanning across all emitted `/api/review/stream` SSE event payloads.
  All 182 backend tests pass cleanly.
- **Remaining Limitations:**
  Redaction applies to generated review evidence and output payloads; the application necessarily retains the submitted patch in memory during the review process. Browser clipboard history or external network interceptors prior to reaching the backend are outside application-level redaction boundaries.
- **Relevant Files / Logs:**
  `backend/app/tools/security_scanner.py`, `backend/tests/test_secret_evidence_redaction_phase324.py`, `docs/audits/DIFFGUARD_PHASE_3_2_4_IMPLEMENTATION_REPORT.md`.

---

## Entry EJ-2026-11-15-01: Independent Security Redaction Verification Audit
- **Date & Scenario:** 2026-11-15 | Phase 3.2.5 Independent Verification Audit
- **Classification:** `SECURITY_AUDIT`
- **Scope & Mode:** Strictly READ-ONLY independent verification of Phase 3.2.4 (*Secret Evidence Redaction & Disclosure Protection*).
- **Probing Methodology:**
  1. Standalone black-box and white-box test executions using isolated synthetic credential token (`audit_synth_sec_9876543210_token`).
  2. Recursive string leakage traversal across all finding schema fields, AST checker, complexity analyzer, test gap analyzer, and standards engine.
  3. Boundary penetration testing across synchronous REST (`POST /api/review`) and asynchronous real-time streaming (`POST /api/review/stream`) endpoints.
  4. Inspection of logging calls across `main.py`, `reviewer_agent.py`, `fallback_engine.py`, `routes.py`, and `security_scanner.py`.
  5. Full regression test suite execution across backend and frontend suites.
- **Audit Findings:**
  1. Surgical span-slicing (`match.span(2)`) consistently replaces credential values with `[REDACTED]` while retaining variable names, operators, and quotation framing.
  2. Non-secret security rules (`SEC-CMD-003`, `SEC-SQLI-001`) preserve verbatim code evidence without unintended redaction.
  3. Zero occurrences of synthetic secret found across full REST API responses, SSE event streams (11 chunks), and log statements.
  4. Frontend UI component (`FindingCard.tsx`) safely renders redacted monospace context blocks without contract breakage.
  5. 182 backend tests passed in 16.19 seconds; 8 frontend tests passed in 0.11 seconds.
- **Verdict:** `A — PASS` (0 credential disclosures across all application boundaries).
- **Relevant Files / Reports:**
  `docs/audits/DIFFGUARD_PHASE_3_2_5_INDEPENDENT_VERIFICATION_REPORT.md`.

---

## Entry EJ-2026-11-15-02: Adversarial End-to-End Secret Disclosure Audit
- **Date & Scenario:** 2026-11-15 | Phase 3.2.6 Adversarial Security Audit
- **Classification:** `SECURITY_AUDIT`
- **Scope & Mode:** Strictly READ-ONLY adversarial penetration audit of Phase 3.2.4 redaction mechanisms across non-standard input topologies, downstream pipelines, and cross-analyzer interactions.
- **Probing Methodology & Findings:**
  1. *Multiple Secrets on One Line (F-SEC-01 — CRITICAL):* `re.search()` only matches the first credential; subsequent credentials on the line remain unredacted in `matched_code`.
  2. *Raw Diff in Prompt (F-SEC-02 — CRITICAL):* `construct_agent_prompt()` places `raw_diff=request.diff_content` directly inside `<untrusted_git_diff>` and transmits unredacted credentials to the external Gemini API.
  3. *AST Syntax Error Context (F-SEC-03 — HIGH):* Malformed syntax on a secret line triggers `SyntaxError`, which `syntax_checker.py` captures via `e.text.strip()` and `fallback_engine.py` embeds into `Finding.location.code_context`, leaking the raw secret into `/api/review` REST and `/api/review/stream` SSE outputs.
  4. *Concatenated Secrets (F-SEC-04 — MEDIUM):* Concatenated strings where prefix matches $\ge 12$ chars redacts the prefix and leaks the rest.
  5. *Logging Isolation:* Application-controlled logs remained clean with zero credential leaks.
- **Verdict:** `FAIL` (Multiple confirmed credential disclosure paths).
- **Phase 4 Authorization:** `NOT AUTHORIZED — REMEDIATION REQUIRED`.
- **Relevant Files / Reports:**
  `docs/audits/PHASE_3_2_6_ADVERSARIAL_SECRET_DISCLOSURE_AUDIT.md`.

---

## Entry EJ-2026-11-15-03: End-to-End Secret Disclosure Remediation
- **Date & Scenario:** 2026-11-15 | Phase 3.2.7 Comprehensive Remediation (Remediating Phase 3.2.6 Audit Findings)
- **Classification:** `SECURITY_REMEDIATION`
- **Scope & Changes:**
  1. *Scanner Multi-Match & Concatenation Hardening (F-SEC-01 & F-SEC-04):* Replaced `re.search()` with `finditer()` in `backend/app/tools/security_scanner.py`, sorting spans in reverse offset order. Extended pattern to match compound string concatenation expressions (`"pre" + "secret"`), redacting compound assigned operands to `"[REDACTED]"`.
  2. *Span Bounds Validation & Fail-Closed Behavior (F-SEC-05):* Added explicit check `0 <= s < e <= len(line)` and fail-closed post-check ensuring no token $\ge 12$ chars survives.
  3. *External LLM Data Boundary Enforcement (F-SEC-02):* Added `sanitize_diff_content()` in `security_scanner.py`. In `backend/app/agent/reviewer_agent.py`, `construct_agent_prompt()` and `ToolDispatcher` receive disclosure-safe diff content. Raw credentials never reach external Gemini API request arguments.
  4. *AST Parser & Fallback Finding Protection (F-SEC-03):* In `backend/app/tools/syntax_checker.py`, sanitized `e.text` and `e.msg` on `SyntaxError` and added unclosed quote pattern. In `backend/app/agent/fallback_engine.py` and `reviewer_agent.py`, added post-synthesis sanitization loops over all finding `code_context`, `why_identified`, and `replacement_code` fields.
  5. *API Boundary Sanitization:* In `backend/app/api/routes.py`, wrapped error exception details in `redact_sensitive_line()`.
- **Verification:**
  1. Created permanent test suite `backend/tests/test_secret_disclosure_remediation_phase327.py` covering all 5 findings across 12 adversarial tests.
  2. Full backend test suite passes: 194 passed in 20.81s.
  3. Frontend test suite passes: 8 passed in 129.75ms.
- **Verdict:** `IMPLEMENTATION COMPLETE — READY FOR INDEPENDENT AUDIT`
- **Phase 4 Authorization:** `PHASE 4: NOT AUTHORIZED BY THIS IMPLEMENTATION`
- **Relevant Files / Reports:**
  `docs/audits/PHASE_3_2_7_IMPLEMENTATION_REPORT.md`, `backend/tests/test_secret_disclosure_remediation_phase327.py`.

---

## Entry EJ-2026-11-15-04: Deleted-Line & Containerized Secret Disclosure Remediation
- **Date & Scenario:** 2026-11-15 | Phase 3.2.9 Targeted Security Hardening (Remediating Phase 3.2.8 Audit Findings)
- **Classification:** `SECURITY_HARDENING`
- **Scope & Changes:**
  1. *F-SEC-06 Remediation (Deleted Git Diff Lines Disclosure — CRITICAL):*
     In `backend/app/tools/security_scanner.py` (`sanitize_diff_content()`), added branch for `elif line.startswith("-") and not line.startswith("---"):`. Strips the `-` diff prefix, sanitizes the sensitive statement via `redact_sensitive_line(line[1:])`, and restores the `-` prefix. Diff file headers (`--- a/...`, `+++ b/...`), hunk headers (`@@`), and metadata remain strictly intact. Ensures deleted credentials in secret rotation/removal PRs are redacted before entering `<untrusted_git_diff>` in LLM prompts, `ToolDispatcher`, `inspect_diff_hunk`, and `inspect_patch_context` tool responses.
  2. *F-SEC-07 Remediation (Containerized Secret Assignment Disclosure — MEDIUM):*
     In `backend/app/tools/security_scanner.py`:
     - Updated variable pattern `SENSITIVE_VAR_PATTERN` to support optional plural suffixes (`api_keys?`, `secrets?`, `tokens?`, `passwords?`, `jwt_secret_keys?`) and quoted dictionary keys (`["']?var["']?`).
     - Updated `UNCLOSED_SECRET_PATTERN` to allow container opening delimiters (`[`, `(`, `{`), dictionary keys (`{"value": "..."}`), and trailing malformed delimiters/comments.
     - Updated `SEC-SECRET-002` pattern in `SECURITY_RULES` to allow container delimiters and dictionary key prefixes between `[:=]` and string literals.
     - In `redact_sensitive_line()`, implemented container element extraction (`SENSITIVE_CONTAINER_START` and `STRING_ELEM_PATTERN`) to find and reverse-replace all string elements within container assignments (including multiple items in lists/tuples), preserving surrounding brackets, punctuation, and non-secret syntax.
     - Preserved reverse-slicing and fail-closed post-checks (`[A-Za-z0-9_\-\.]{12,}`).
     In `backend/app/tools/syntax_checker.py`:
     - Added `"unterminated"` keyword to `SyntaxError` exception checks, ensuring containerized syntax errors have `text` and `msg` safely redacted.
  3. *Preservation of F-SEC-01 Through F-SEC-05:*
     All invariants preserved: multi-secret reverse slicing without drift (F-SEC-01), LLM prompt masking (F-SEC-02), syntax exception protection (F-SEC-03), compound concatenation redaction (F-SEC-04), and strict bounds fail-closed checks (F-SEC-05).
- **Verification:**
  1. Created permanent regression test suite `backend/tests/test_secret_disclosure_remediation_phase329.py` containing 24 comprehensive tests covering all 10 containerized scenarios, deleted line diffs, tool boundaries, REST, and SSE streams (24/24 passing in 0.79s).
  2. Full backend regression test suite passes: 218 passed in 9.51s (`python -m pytest backend/tests -v`).
  3. Frontend test suite passes: 8 passed in 95.5ms (`npm test` in `frontend/`).
- **Remaining Limitations:**
  Detection relies on identifier semantics (`api_key`, `secret`, `password`, `token`, `jwt`, `private_key`) combined with assignments to string literals or compound string expressions ($\ge 12$ characters). Non-descriptive single-letter variables assigned in obscure languages or non-string object constructors remain outside heuristic regex scope.
- **Verdict:** `IMPLEMENTATION COMPLETE — READY FOR INDEPENDENT AUDIT`
- **Phase 4 Authorization:** `PHASE 4: NOT AUTHORIZED BY THIS IMPLEMENTATION (Awaiting Independent Audit)`
- **Relevant Files / Reports:**
  `docs/audits/DIFFGUARD_PHASE_3_2_9_IMPLEMENTATION_REPORT.md`, `backend/tests/test_secret_disclosure_remediation_phase329.py`.

---

## Entry EJ-2026-11-15-05: Stateful Diff Redaction & Multiline Secret Disclosure Remediation
- **Date & Scenario:** 2026-11-15 | Phase 3.2.11 Targeted Remediation (Remediating Phase 3.2.10 Audit Findings)
- **Classification:** `SECURITY_HARDENING`
- **Scope & Changes:**
  1. *F-SEC-08 Remediation (Hyphenated Deleted Diff Line Redaction — CRITICAL):*
     - Replaced naive string-prefix heuristics with structural unified-diff state tracking in `backend/app/tools/security_scanner.py` (`sanitize_diff_content()`).
     - Tracks `in_hunk` state: file headers (`--- a/...`, `+++ b/...`) and metadata are recognized strictly outside hunks.
     - Inside hunks (after `@@`), lines starting with `-` are classified strictly as deleted source lines, stripping exactly one leading `-`, passing the content through old-side scope tracking, and restoring `-`.
     - Seamlessly handles SQL/Lua comments (`---API_KEY = "..."`), decrement operators (`---count`), and YAML bullets (`--- API_KEY = "..."`) without disclosure bypass.
  2. *F-SEC-09 Remediation (Multi-line Container Scope Tracking — HIGH):*
     - Implemented `ContainerScopeTracker` in `backend/app/tools/security_scanner.py` tracking delimiter depth (`[`, `]`, `(`, `)`, `{`, `}`) across lines.
     - Quote-aware and escape-aware via `is_quote_count_odd()`, ignoring brackets inside string literals and inline comments.
     - Preserves dictionary keys while redacting values via bounded lookahead (`tail = text[e:].lstrip(); if tail.startswith(':'): continue`).
     - In `sanitize_diff_content()`, maintains independent `old_scope` and `new_scope` trackers to prevent bleed across interleaved added, deleted, and context lines.
     - Implemented `sanitize_code_snippet()` for multi-line AST check in `backend/app/tools/syntax_checker.py`, neutralizing `SyntaxError.text`, `e.msg`, and `Finding.location.code_context` leaks.
  3. *Short Credential Redaction Separation:*
     - Disconnected static detection thresholds from disclosure redaction.
     - Removed `{12,}` minimum length constraint from disclosure redaction regexes (`STANDALONE_SECRET_ASSIGNMENT`, `UNCLOSED_SECRET_PATTERN`, `STRING_ELEM_PATTERN`).
     - Any string literal assigned to recognized sensitive variables (`API_KEY = "x"`, `API_KEY = "short"`) is sanitized to `"[REDACTED]"`.
     - Static scanner rule `SEC-SECRET-002` retains length filtering to prevent static analysis noise.
     - Added `is_index_inside_quote()` to prevent false-positive redaction/detection of sensitive variable names inside SQL query strings or print statements.
  4. *Preservation of F-SEC-01 Through F-SEC-07:*
     All invariants preserved across tools, REST endpoints, and SSE streams.
- **Verification:**
  1. Created permanent regression test suite `backend/tests/test_secret_disclosure_remediation_phase3211.py` with 25 comprehensive tests (25/25 passed in 0.76s).
  2. Full backend regression test suite passed: 243 passed in 9.35s (`python -m pytest backend/tests -v`).
  3. Frontend test suite passed: 8 passed in 87.3ms (`npm --prefix frontend test -- --watchAll=false`).
- **Verdict:** `IMPLEMENTATION COMPLETE — READY FOR INDEPENDENT AUDIT`
- **Phase 4 Authorization:** `PHASE 4: NOT AUTHORIZED BY THIS IMPLEMENTATION (Awaiting Independent Audit)`
- **Relevant Files / Reports:**
  `docs/audits/DIFFGUARD_PHASE_3_2_11_IMPLEMENTATION_REPORT.md`, `backend/tests/test_secret_disclosure_remediation_phase3211.py`, `backend/app/tools/security_scanner.py`, `backend/app/tools/syntax_checker.py`.

---

## Entry EJ-2026-11-15-06: Targeted Bug Fixes & Assignment Readiness (Phase 3.2.13)
- **Date & Scenario:** 2026-11-15 | Phase 3.2.13 Targeted Bug Fixes & Assignment Readiness
- **Classification:** `ASSIGNMENT_READINESS`
- **Scope & Changes:**
  1. *SQL f-string false positive regression resolution:*
     - Implemented `is_index_inside_quote(line: str, target_idx: int) -> bool` in `backend/app/tools/security_scanner.py` tracking string quote context up to the matched identifier, accounting for escaping and quotes (`"`, `'`, `` ` ``).
     - Guarded `UNCLOSED_SECRET_PATTERN` in `scan_security_issues()` and `redact_single_line_secrets()` so it only evaluates when `is_quote_count_odd()` is True and the identifier is not inside quotes.
     - Filtered matches in `scan_security_issues()` so identifiers like `password` embedded in SQL query strings (`raw_query = f"SELECT ... AND password = '{password_hash}'"`) are not misdetected as credential assignments.
     - Resolved `test_secret_detection_refinement_phase321.py::TestEvidenceAndLocationIntegrity::test_scenario_a_end_to_end_detects_all_three_defects` (`assert 3 == 3` now passes cleanly).
  2. *F-SEC-10 Remediation (JavaScript / TypeScript ES6 Backtick Delimiter Support):*
     - Defined `STRING_LITERAL = r"""(?:"[^"\r\n]*"|'[^'\r\n]*'|`[^`\r\n]*`)"""` across `STANDALONE_SECRET_ASSIGNMENT` and `STRING_ELEM_PATTERN`.
     - Extended `SENSITIVE_VAR_PATTERN`, `UNCLOSED_SECRET_PATTERN`, `is_quote_count_odd()`, and `_compute_net_delimiters()` to recognize and track backtick quotes.
     - Updated `redact_single_line_secrets()` and `_replace_closed_strings()` to format backtick replacements cleanly as `` `[REDACTED]` `` while preserving surrounding syntax.
     - Preserves ordinary non-sensitive backtick template literals (e.g., `` `Hello, ${name}!` ``).
  3. *Comprehensive Regression & Suite Verification:*
     - Authored dedicated test suite `backend/tests/test_phase3213_fixes.py` covering SQL f-string false positive prevention, backtick assignments, interpolation, short credentials, containers, and non-sensitive strings.
     - Executed full test suite: all 251 backend pytest tests and 8 frontend tests passing (100% pass, 0 failures, 0 regressions).
- **Verification:**
  1. `backend/tests/test_phase3213_fixes.py`: 8 passed in 0.03s.
  2. `backend/tests/test_secret_detection_refinement_phase321.py`: 19 passed in 0.52s.
  3. `backend/tests/test_secret_disclosure_remediation_phase3211.py`: 25 passed in 0.76s.
  4. Full backend test suite (`python -m pytest backend/tests`): 251 passed in 53.79s.
  5. Frontend test suite (`npm --prefix frontend test -- --watchAll=false`): 8 passed in 139ms.
- **Verdict:** `PHASE 3.2.13 COMPLETE — DIFFGUARD READY FOR ASSIGNMENT DEMONSTRATION`
- **Phase 4 Status:** `NOT AUTHORIZED AND NOT REQUIRED FOR ASSIGNMENT READINESS`
- **Relevant Files / Reports:**
  `docs/audits/DIFFGUARD_PHASE_3_2_13_IMPLEMENTATION_REPORT.md`, `backend/tests/test_phase3213_fixes.py`, `backend/app/tools/security_scanner.py`.








