# DiffGuard — Phase 3.2.6 Adversarial End-to-End Secret Disclosure Audit Report

**Repository:** `C:\Users\HP\OneDrive\Documents\Diffguard`  
**Baseline Git Commit:** `5993e7fa6e20ec71c63d9ab4b41db3feaf25f842`  
**Phase Under Audit:** Phase 3.2.4 — Secret Evidence Redaction & Disclosure Protection  
**Auditor Roles:** Principal AI Security Engineer, Code Review Systems Security Auditor, and Senior Backend Architect  
**Audit Date:** November 15, 2026  
**Audit Mode:** STRICT READ-ONLY SECURITY AUDIT (No modifications to application code or tracked tests)  
**Deliverable File:** `docs/audits/PHASE_3_2_6_ADVERSARIAL_SECRET_DISCLOSURE_AUDIT.md`  

---

## 1. Executive Verdict

### Final Audit Verdict: **FAIL**

**Basis for Verdict:**  
The adversarial investigation identified **three distinct, reproducible credential disclosure paths** where raw synthetic secrets escape the application's sanitization boundary and are disclosed in external outputs:
1. **Multiple Secrets on One Line (F-SEC-01 — CRITICAL):** `scan_security_issues()` uses `re.search()`, matching only the first secret on a line. Subsequent secrets on the same line are left completely unredacted in `matched_code`, entering downstream findings and API payloads.
2. **Raw Diff Transmission to External LLM (F-SEC-02 — CRITICAL):** While the security scanner redacts `matched_code` in `tool_evidence`, the agent prompt constructor (`construct_agent_prompt`) places the raw, unredacted git diff (`request.diff_content`) verbatim inside `<untrusted_git_diff>` and transmits it to the external Gemini API (`genai.Client`).
3. **AST Parser Syntax Error Exposure (F-SEC-03 — HIGH):** When a diff line contains a secret alongside an unclosed parenthesis or bracket, `ast.parse` triggers a syntax error. `syntax_checker.py` captures `e.text.strip()` (which contains the raw secret), and `fallback_engine.py` embeds it into `Finding.location.code_context`, broadcasting the unredacted credential in REST API and SSE stream payloads.

---

## 2. Scope & Environment

### 2.1 Git Environment & Working Tree Status
- **Repository Path:** `C:\Users\HP\OneDrive\Documents\Diffguard`
- **Head Commit:** `5993e7fa6e20ec71c63d9ab4b41db3feaf25f842`
- **Working Tree:** Intact progressive implementation files from Phases 1 through 3.2.4 preserved without regression.
- **Python Runtime:** Python 3.12.7 (win32), pytest 9.1.1
- **Node Runtime:** Node v24.19.0

### 2.2 Test Suite Execution Baseline
- **Backend Test Suite:** `python -m pytest backend/tests -q`
  - **Result:** 182 passed in 29.33s (Exit Code: 0)
- **Frontend Test Suite:** `npm --prefix frontend test -- --watchAll=false`
  - **Result:** 8 passed in 0.19s (Exit Code: 0)

---

## 3. Detailed Audit Findings

### Finding F-SEC-01: Multiple Credentials on a Single Line Evade Full Redaction (CRITICAL)

- **Severity:** Critical
- **Affected Component:** `backend/app/tools/security_scanner.py`
- **Source Location:** [security_scanner.py:111-123](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/tools/security_scanner.py#L111-L123)
- **Attack / Failure Scenario:**
  A developer commits a configuration line containing two or more credentials or tokens on the same line, e.g.:
  ```python
  API_KEY = "audit_synth_sec_9876543210_alpha" and SECRET_KEY = "audit_synth_sec_9876543210_beta"
  ```
- **Reproduction Evidence:**
  Executing `scan_security_issues()` against this input line:
  ```python
  match = rule["pattern"].search(clean_line)
  val_start, val_end = match.span(2)
  evidence_code = clean_line[:val_start] + "[REDACTED]" + clean_line[val_end:]
  ```
  `rule["pattern"].search()` halts at the first match (`API_KEY`). Only the first group 2 span is substituted.
- **Observed Result:**
  ```python
  matched_code = 'API_KEY = "[REDACTED]" and SECRET_KEY = "audit_synth_sec_9876543210_beta"'
  ```
  The second secret `audit_synth_sec_9876543210_beta` remains 100% intact and unredacted in finding evidence.
- **Expected Result:**
  All matching credential values on the line must be redacted (e.g., via `re.finditer` or iterative substitution), or the entire line must fail closed.
- **Confirmed Credential Disclosure:** **YES**
- **Recommended Remediation (Audit Only — Do Not Implement):**
  Use `re.finditer` to collect all non-overlapping match spans for `SEC-SECRET-002` in reverse offset order, redacting every capture group 2, or replace `search` with iterative redaction.

---

### Finding F-SEC-02: Unredacted Raw Diff Transmitted to External LLM API (CRITICAL)

- **Severity:** Critical
- **Affected Component:** `backend/app/agent/reviewer_agent.py` & `backend/app/agent/prompts.py`
- **Source Location:** 
  - [reviewer_agent.py:361-367](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/agent/reviewer_agent.py#L361-L367)
  - [prompts.py:80-84](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/agent/prompts.py#L80-L84)
- **Attack / Failure Scenario:**
  A user submits a PR containing a hardcoded secret for review. The application is configured with a Gemini API key or the user supplies one via `request.api_key`.
- **Reproduction Evidence:**
  In `reviewer_agent.py`:
  ```python
  prompt = construct_agent_prompt(
      parsed_diff_summary=files_summary,
      raw_diff=request.diff_content,
      tool_evidence=tool_evidence_str,
      ...
  )
  ```
  In `prompts.py`:
  ```python
  ### UNTRUSTED GIT DIFF TO REVIEW
  <untrusted_git_diff>
  {raw_diff}
  </untrusted_git_diff>
  ```
  In `reviewer_agent.py`:
  ```python
  conversation_history: List[types.Content] = [
      types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
  ]
  # Dispatched to active_client.models.generate_content(...)
  ```
- **Observed Result:**
  While `tool_evidence_str` contains `JWT_SECRET_KEY = "[REDACTED]"`, the surrounding prompt embeds the raw unredacted diff string `request.diff_content`. The raw credential `audit_synth_sec_9876543210_alpha` is transmitted in plaintext to the external model API endpoint.
- **Expected Result:**
  The model input prompt must not receive raw unredacted credential values. Credential lines within the raw diff should be pre-sanitized before prompt assembly, or an explicitly documented security policy must define the model boundary as an authorized trusted processing tier.
- **Confirmed Credential Disclosure:** **YES** (to external LLM provider API)
- **Recommended Remediation (Audit Only — Do Not Implement):**
  Implement diff sanitization prior to `construct_agent_prompt()` by masking secret lines detected by `security_scanner`, or document the third-party LLM boundary in security disclosures.

---

### Finding F-SEC-03: Malformed Python Source with AST Syntax Error Leaks Secret into REST & SSE Responses (HIGH)

- **Severity:** High
- **Affected Component:** `backend/app/tools/syntax_checker.py` & `backend/app/agent/fallback_engine.py`
- **Source Location:**
  - [syntax_checker.py:33-41](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/tools/syntax_checker.py#L33-L41)
  - [fallback_engine.py:88-92](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/agent/fallback_engine.py#L88-L92)
- **Attack / Failure Scenario:**
  A developer accidentally commits a secret line with malformed syntax, such as an unclosed parenthesis or bracket:
  ```python
  +JWT_SECRET_KEY = "audit_synth_sec_9876543210_alpha" (
  ```
- **Reproduction Evidence:**
  1. `syntax_checker.py` catches `SyntaxError: '(' was never closed`.
  2. Because `"was never closed"` matches the syntax trap filter, it creates an issue:
     ```python
     "text": e.text.strip() # Contains 'JWT_SECRET_KEY = "audit_synth_sec_9876543210_alpha" ('
     ```
  3. `fallback_engine.py` processes `tool_results["syntax_findings"]`:
     ```python
     location=CodeLocation(
         file_path=syn.get("file_path", "unknown"),
         start_line=syn.get("adjusted_line", syn.get("line_number", 1)),
         code_context=syn.get("text", "")
     )
     ```
  4. The unredacted string is assigned to `code_context`.
- **Observed Result:**
  Probing `POST /api/review` via `TestClient`:
  - `response.status_code`: 200 OK
  - `response.json()["findings"][1]["location"]["code_context"]`: `JWT_SECRET_KEY = "audit_synth_sec_9876543210_alpha" (`
  - `secret_leaked_in_api_response`: **TRUE**
- **Expected Result:**
  Any source code snippet attached to findings by `syntax_checker` or `fallback_engine` must undergo secret sanitization/redaction before exposure.
- **Confirmed Credential Disclosure:** **YES**
- **Recommended Remediation (Audit Only — Do Not Implement):**
  Apply secret redaction to `syn.get("text")` or pass `code_context` through a centralized redaction utility before attaching it to `Finding`.

---

### Finding F-SEC-04: String Concatenation Evades Full Value Redaction (MEDIUM)

- **Severity:** Medium
- **Affected Component:** `backend/app/tools/security_scanner.py`
- **Source Location:** [security_scanner.py:28-31](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/tools/security_scanner.py#L28-L31)
- **Attack / Failure Scenario:**
  A developer splits or concatenates a credential:
  ```python
  +API_KEY = "audit_prefix_" + "audit_synth_sec_9876543210_alpha"
  ```
- **Reproduction Evidence:**
  The regex matches `"audit_prefix_"` (which has 13 characters, $\ge 12$).
  It redacts `"audit_prefix_"`, producing:
  ```python
  matched_code = 'API_KEY = "[REDACTED]" + "audit_synth_sec_9876543210_alpha"'
  ```
- **Observed Result:**
  The true credential operand `"audit_synth_sec_9876543210_alpha"` is preserved intact in `matched_code`.
- **Expected Result:**
  Complex assignments should either fail closed or detect compound string literals.
- **Confirmed Credential Disclosure:** **YES**
- **Recommended Remediation (Audit Only — Do Not Implement):**
  Enhance detection patterns to identify concatenated string expressions or sanitize the entire assignment RHS.

---

### Finding F-SEC-05: Non-Throwing Negative Span Handling Risk in Redaction Slicing Logic (LOW)

- **Severity:** Low
- **Affected Component:** `backend/app/tools/security_scanner.py`
- **Source Location:** [security_scanner.py:116-118](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/tools/security_scanner.py#L116-L118)
- **Attack / Failure Scenario:**
  If a regex pattern has an optional capture group that does not participate in a match, Python's `match.span(group)` returns `(-1, -1)`.
- **Reproduction Evidence:**
  Evaluating `clean_line[:-1] + "[REDACTED]" + clean_line[-1:]`:
  In Python, negative slicing does NOT throw an `IndexError`.
  For `clean_line = 'TOKEN = "12345678901234"'`:
  Result: `'TOKEN = "1234567890123[REDACTED]"'`
  The entire secret except the trailing character is exposed.
- **Observed Result:**
  While the current `SEC-SECRET-002` regex strictly requires group 2 to participate, the slicing logic relies on a pattern guarantee rather than asserting `val_start >= 0 and val_end >= val_start`.
- **Expected Result:**
  The code must explicitly check `if val_start < 0 or val_end < 0: raise ValueError("Non-participating group")`.
- **Confirmed Credential Disclosure:** **NO** (mitigated by current regex structure, but structurally fragile).
- **Recommended Remediation (Audit Only — Do Not Implement):**
  Add explicit validation `if val_start < 0 or val_end < val_start: ...` before slicing.

---

## 4. Verification Matrix

| Investigation Area | Test Case / Scenario | Result | Evidence / Observed Behavior |
| :--- | :--- | :---: | :--- |
| **V-01: Regex Capture Integrity** | Group 2 participating (valid secret) | **PASS** | Group 2 correctly sliced and replaced with `[REDACTED]` |
| **V-01: Regex Capture Integrity** | Non-participating group simulation | **FAIL** | Negative index slice does not throw; leaks characters |
| **V-01: Regex Capture Integrity** | Multiple secrets on one line | **FAIL** | Only first secret redacted; second secret leaked intact |
| **V-02: Pipeline Propagation** | Tool evidence in prompt | **PASS** | `tool_evidence_str` contains redacted secret |
| **V-02: Pipeline Propagation** | Raw diff in LLM prompt | **FAIL** | Raw unredacted diff embedded in prompt to Gemini API |
| **V-02: Pipeline Propagation** | Heuristic fallback input | **PASS** | Fallback uses parsed hunks & tool findings |
| **V-03: AST Exceptions** | Unclosed parenthesis on secret line | **FAIL** | `syntax_checker` text leaks raw secret to REST API |
| **V-03: AST Exceptions** | Secret followed by malformed def | **PASS** | No syntax issue emitted; secret detected & redacted |
| **V-04: Runtime Logging** | Application logs on normal review | **PASS** | No credentials found in 7,031 bytes of captured logs |
| **V-04: Runtime Logging** | Application logs on malformed review | **PASS** | Zero credentials logged in log records |
| **V-05: Adversarial Matrix** | Single quotes assignment | **PASS** | `API_KEY = '[REDACTED]'` |
| **V-05: Adversarial Matrix** | Double quotes assignment | **PASS** | `API_KEY = "[REDACTED]"` |
| **V-05: Adversarial Matrix** | Spaces around assignment operator | **PASS** | `API_KEY    =    "[REDACTED]"` |
| **V-05: Adversarial Matrix** | Colon assignment syntax | **PASS** | `API_KEY: "[REDACTED]"` |
| **V-05: Adversarial Matrix** | Trailing comment on secret line | **PASS** | `API_KEY = "[REDACTED]" # secret token` |
| **V-05: Adversarial Matrix** | String concatenation assignment | **FAIL** | Partial match leaves remainder of secret unredacted |
| **V-05: Adversarial Matrix** | Negative identifiers (`user_key`) | **PASS** | Correctly ignored (0 false positive matches) |

---

## 5. Synthetic Credential Disclosure Ledger

| Synthetic Credential Token | Boundary Tested | Disclosed? | Disclosure Location / Context |
| :--- | :--- | :---: | :--- |
| `audit_synth_sec_9876543210_alpha` | Scanner (`matched_code`) | **NO** | Replaced with `[REDACTED]` |
| `audit_synth_sec_9876543210_beta` | Scanner (second secret on line) | **YES** | `matched_code` in `SEC-SECRET-002` finding |
| `audit_synth_sec_9876543210_alpha` | LLM API Input (`prompt`) | **YES** | `<untrusted_git_diff>` in agent prompt |
| `audit_synth_sec_9876543210_alpha` | REST API (`/api/review`) | **YES** | `findings[1].location.code_context` via AST syntax error |
| `audit_synth_sec_9876543210_alpha` | Streaming SSE (`/api/review/stream`) | **YES** | Serialized `completed` event via AST syntax error |
| `audit_synth_sec_9876543210_alpha` | Application Logger (`logging`) | **NO** | 0 occurrences across captured logs |

---

## 6. Threat-Boundary Statement

### What This Audit Confirms
1. For single, well-formed assignment lines matching `SEC-SECRET-002`, `scan_security_issues()` successfully replaces the credential value with `[REDACTED]`.
2. Application logging across `main.py`, `reviewer_agent.py`, `routes.py`, and `security_scanner.py` does not emit credential values.
3. Negative controls (`user_key`, `cache_key`, `primary_key`) are properly ignored by the detector.

### What This Audit Disproves
1. **The claim that credentials cannot leak into REST API responses is FALSE:** Malformed Python source syntax exposes raw secrets through `syntax_checker.py` and `fallback_engine.py`.
2. **The claim that credentials cannot leak into finding evidence is FALSE:** Committing two secrets on the same line leaks the second secret unredacted.
3. **The claim that credentials do not reach downstream AI processing is FALSE:** Raw diffs containing credentials are sent verbatim in user prompts to the Gemini model API.

---

## 7. Phase 4 Authorization Recommendation

### Recommendation: **NOT AUTHORIZED — REMEDIATION REQUIRED**

**Justification:**  
Phase 3.2.4 (*Secret Evidence Redaction & Disclosure Protection*) exhibits high-severity and critical-severity credential disclosure vulnerabilities under adversarial conditions. Advancing to Phase 4 (Production Readiness & Release Packaging) prior to remediating F-SEC-01, F-SEC-02, and F-SEC-03 would deploy an insecure credential redaction architecture.

Remediation must be scheduled and verified in a subsequent targeted phase before Phase 4 can be considered.
