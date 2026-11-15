# DiffGuard — Phase 3.2.3 Source-Level Regex Sanity Verification Report

**Project:** DiffGuard — AI-Powered Git Diff & Pull Request Review Agent  
**Repository:** `C:\Users\HP\OneDrive\Documents\Diffguard`  
**Baseline Git Commit:** `5993e7fa6e20ec71c63d9ab4b41db3feaf25f842`  
**Audit Phase:** 3.2.3 — Source-Level Regex Sanity Verification  
**Auditor Roles:** Principal AI Engineer, Senior Application Security Auditor, Python Language & Runtime Specialist  
**Audit Mode:** Strictly Read-Only Source & Runtime Sanity Verification  
**Date:** November 14, 2026

---

## 1. Executive Verdict

### **Verdict: VERIFIED — FULL CONGRUENCE & EVIDENCE INTEGRITY**

The implementation of rule `SEC-SECRET-002` in `backend/app/tools/security_scanner.py` was inspected directly at the source, bytecode, and execution levels.

### Key Conclusions:
1. **Source & Documentation Congruence:** The regex compiled in `backend/app/tools/security_scanner.py` is identical character-for-character to the expression reported in the Phase 3.2.1 and Phase 3.2.2 audit reports. There is **no discrepancy** between the tested regex, the documented regex, and the active production implementation.
2. **Capturing Group Hierarchy:** The compiled regex contains exactly **two capturing groups**:
   - `Group 1`: The credential identifier / variable name (e.g. `'JWT_SECRET_KEY'`, `'SECRET_KEY'`, `'password'`).
   - `Group 2`: The credential string value (min 12 characters, e.g. `'prod_jwt_super_secret_key_1234567890'`).
   - All internal suffix alternations (`(?:[_-]?(?:key|token))?`, `(?:key|token)`, `(?:[_-]?key)?`) are strictly non-capturing groups `(?:...)`.
3. **Evidence Construction:** The scanner uses `match = rule["pattern"].search(clean_line)` as an identification gate, and assigns `matched_code = clean_line.strip()`. The evidence cited in findings is the full, clean line from the diff hunk, preserving context without truncation.
4. **Focused Test Execution:** All **19 / 19 focused regression tests** in `test_secret_detection_refinement_phase321.py` passed cleanly in 1.06s.
5. **Git State:** The Git working tree remains completely untouched by this verification.

---

## 2. Exact Source Lines Defining `SEC-SECRET-002`

In `backend/app/tools/security_scanner.py`, lines 22 through 33 define `SEC-SECRET-002`:

```python
    {
        "id": "SEC-SECRET-002",
        "cwe": "CWE-798",
        "name": "Hardcoded Secret / Credential",
        "severity": "CRITICAL",
        "description": "Hardcoded API key, token, private key, or password detected in source code.",
        "pattern": re.compile(
            r"""(?i)(api[_-]?key|secret(?:[_-]?(?:key|token))?|token|password|passwd|jwt[_-]?secret(?:[_-]?key)?|private[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{12,})["']""",
            re.MULTILINE
        ),
        "remediation": "Load sensitive credentials from environment variables or a secure secret manager (e.g., os.getenv('API_KEY'))"
    },
```

---

## 3. Compiled Regex Pattern and Python `repr()`

Direct runtime inspection of the compiled pattern object in `backend/app/tools/security_scanner.py`:

```
Pattern string:
(?i)(api[_-]?key|secret(?:[_-]?(?:key|token))?|token|password|passwd|jwt[_-]?secret(?:[_-]?key)?|private[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{12,})["']

repr(pat):
re.compile('(?i)(api[_-]?key|secret(?:[_-]?(?:key|token))?|token|password|passwd|jwt[_-]?secret(?:[_-]?key)?|private[_-]?key)\\s*[:=]\\s*["\']([A-Za-z0-9_\\-\\.]{12,})["\']', re.IGNORECASE|re.MULTILINE)

Flags: 42 (re.IGNORECASE: True, re.MULTILINE: True)
Groups count: 2
Named groups (groupindex): {}
```

---

## 4. Capturing Group and Non-Capturing Group Architecture

The regular expression is structured as follows:

| Group # | Syntax | Type | Purpose / Matched Content |
|:---:|---|:---:|---|
| **0** | *(Whole Expression)* | Full Match | Entire assignment statement from variable to closing quote |
| **1** | `(api[_-]?key|secret(?:...)?|token|password|passwd|jwt[_-]?secret(?:...)?|private[_-]?key)` | **Capturing** | Credential identifier / variable name |
| — | `(?:[_-]?(?:key|token))` | Non-capturing | Optional compound delimiter and suffix for `secret` |
| — | `(?:key|token)` | Non-capturing | Sub-alternation choosing between `key` and `token` |
| — | `(?:[_-]?key)` | Non-capturing | Optional compound delimiter and suffix for `jwt[_-]?secret` |
| **2** | `([A-Za-z0-9_\-\.]{12,})` | **Capturing** | Credential string value ($\ge 12$ alphanumeric, underscore, hyphen, or dot chars) |

**Confirmation:** The credential value is explicitly captured as **Group 2**.

---

## 5. Empirical Execution Against Test Strings

The compiled pattern was executed against the exact strings specified in the audit mandate:

### 1. `JWT_SECRET_KEY = "prod_jwt_super_secret_key_1234567890"`
- **Result:** **MATCH**
- **`span`:** `(0, 55)`
- **`group(0)`:** `'JWT_SECRET_KEY = "prod_jwt_super_secret_key_1234567890"'`
- **`group(1)`:** `'JWT_SECRET_KEY'`
- **`group(2)`:** `'prod_jwt_super_secret_key_1234567890'`
- **`groups()` tuple:** `('JWT_SECRET_KEY', 'prod_jwt_super_secret_key_1234567890')`

### 2. `AWS_SECRET_KEY = "example_aws_secret_value_123456"`
- **Result:** **MATCH**
- **`span`:** `(4, 50)`
- **`group(0)`:** `'SECRET_KEY = "example_aws_secret_value_123456"'`
- **`group(1)`:** `'SECRET_KEY'`
- **`group(2)`:** `'example_aws_secret_value_123456'`
- **`groups()` tuple:** `('SECRET_KEY', 'example_aws_secret_value_123456')`

### 3. `password = "secret_password_12345"`
- **Result:** **MATCH**
- **`span`:** `(0, 34)`
- **`group(0)`:** `'password = "secret_password_12345"'`
- **`group(1)`:** `'password'`
- **`group(2)`:** `'secret_password_12345'`
- **`groups()` tuple:** `('password', 'secret_password_12345')`

### 4. `user_key = "customer_reference_value_12345"`
- **Result:** **NO MATCH (CLEAN)**
- **Findings emitted:** `0`
- **Explanation:** `user_key` does not match `api_key`, `secret_key`, or `private_key`. The pattern does not allow standalone `key`.

---

## 6. Scanner Extraction and `matched_code` Construction

In `backend/app/tools/security_scanner.py` (lines 110–123):

```python
clean_line = line.lstrip("+ ")
match = rule["pattern"].search(clean_line)
if match:
    findings.append({
        "rule_id": rule["id"],
        "cwe": rule["cwe"],
        "name": rule["name"],
        "severity": rule["severity"],
        "description": rule["description"],
        "file_path": file_path,
        "line_number": line_no,
        "matched_code": clean_line.strip(),
        "remediation": rule["remediation"]
    })
```

### Trace Observations:
1. `match` is used as a truthiness predicate (`if match:`).
2. The finding's `matched_code` is constructed from `clean_line.strip()`.
3. In the case of `AWS_SECRET_KEY = "..."`, even though `match.group(0)` spans `SECRET_KEY = "..."` (offset 4 to 50), the finding's `matched_code` contains the **full line**: `AWS_SECRET_KEY = "example_aws_secret_value_123456"`.
4. Downstream in `reviewer_agent.py` and `fallback_engine.py`, `matched_code` is forwarded as `location.code_context`, providing clean, complete evidence for the review finding card.

---

## 7. Analysis of the Discrepancy Question

The verification question asked whether the reported regex discrepancy is:
- A documentation/rendering issue;
- An actual source-code issue; or
- A mismatch between the tested regex and production implementation.

### Empirical Finding:
- **No Discrepancy Exists:** The source code in `backend/app/tools/security_scanner.py` at line 29:
  ```python
  r"""(?i)(api[_-]?key|secret(?:[_-]?(?:key|token))?|token|password|passwd|jwt[_-]?secret(?:[_-]?key)?|private[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{12,})["']"""
  ```
  matches the Phase 3.2.1 report and Phase 3.2.2 audit report identically.
- **Escaping Nuances:** In standard Python `repr()`, backslashes appear doubled (`\\s`, `\\-`, `\\.`, `[\"\\']`), whereas in raw Python strings (`r"""..."""`) and Markdown code blocks they appear single (`\s`, `\-`, `\.`). This is a standard Python representation convention, not a source-code divergence or implementation defect.

---

## 8. Focused Regression Test Suite Execution

Executed without modifying any files:

```
Command: python -m pytest backend/tests/test_secret_detection_refinement_phase321.py -v
Platform: win32 -- Python 3.12.7, pytest-9.1.1, pluggy-1.6.0
Duration: 1.06s
Passed: 19
Failed: 0
Errors: 0
```

### Test Case Status:
- `TestCompoundSecretDetection`: 5 passed (`JWT_SECRET_KEY`, `AWS_SECRET_KEY`, `DATABASE_PASSWORD`, `API_TOKEN`, `PRIVATE_KEY`).
- `TestExistingSecretDetectionPreserved`: 6 passed (`JWT_SECRET`, `api_key`, `token`, `password`, `SECRET`, `client_secret`).
- `TestFalsePositiveResistance`: 6 passed (10 variables tested, all clean).
- `TestEvidenceAndLocationIntegrity`: 2 passed (Scenario A 3/3 defects confirmed, Scenario B clean).

---

## 9. Git Working Tree Integrity

Audited via `git status --short`:
- No files were modified, staged, reverted, or committed during this verification.
- The Git working tree remains in its exact prior state.
- Baseline commit: `5993e7fa6e20ec71c63d9ab4b41db3feaf25f842`.

---

## 10. Verification Verdict & Next Phase Readiness

### **FINAL VERDICT: VERIFIED**

The `SEC-SECRET-002` implementation is accurate, syntactically clean, mathematically consistent with its group definitions, and fully verified by automated tests and runtime inspection.

**Status:** Standing by for explicit user authorization before proceeding to Phase 4.

