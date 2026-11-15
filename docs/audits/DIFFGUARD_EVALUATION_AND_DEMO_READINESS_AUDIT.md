# DiffGuard — Evaluation & Demo Readiness Audit
## Review Accuracy, Evidence Integrity, Agent Behavior & Assignment Readiness
*(Audited & Corrected for Evidence Integrity — November 14, 2026)*

**Project:** DiffGuard — AI-Powered Git Diff & Pull Request Review Agent  
**Repository:** `C:\Users\HP\OneDrive\Documents\Diffguard`  
**Baseline Git Commit:** `5993e7fa6e20ec71c63d9ab4b41db3feaf25f842`  
**Audit Date:** November 14, 2026  
**Audit Type:** Empirical Evaluation, Evidence Verification & Demo Readiness Assessment  
**Audit Roles:** Principal AI Engineer, AI Agent Evaluation Specialist, Software Quality Auditor, Application Security Reviewer  

---

## 1. Executive Summary & Corrected Verdict

### Final Readiness Verdict: A — DEMO READY (With Stated Evidence Limitations)

DiffGuard is ready for live demonstration as an applied engineering project. Its deterministic analyzers, AST syntax checks, cyclomatic complexity calculations, test requirement analyzers, and two-phase Gemini function-calling architecture operate reliably without breaking the frontend or backend.

However, all claims must be grounded in verified evidence rather than synthetic assertion ratios:
- **Test Suite Integrity:** `TEST VERIFIED` — 85/85 backend tests passed (46.29s offline mock suite); 5/5 frontend tests passed (103ms); Next.js frontend builds successfully (0 errors).
- **Framework Discrepancy Corrected:** The frontend runs **Next.js 15.5.29** and **React 19.0.0** (defined as `"next": "^15.1.0"` in `package.json`), resolving previous documentation errors that misidentified it as Next.js 14.
- **Ground-Truth Evaluation (Deterministic Fallback Engine):**
  - Evaluated across the 5 bundled sample pull requests in [sample_diffs.py](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/samples/sample_diffs.py).
  - Out of 10 intended ground-truth defects across defective samples, the deterministic fallback engine detected **7 True Positives** and missed **3 False Negatives** (hardcoded secret with non-standard variable name, unawaited async custom webhook call, and multi-line exception silencing).
  - Observed False Positives: **0**.
  - **Finding-Level Precision:** **100.0%** ($7 / 7$).
  - **Finding-Level Recall:** **70.0%** ($7 / 10$).
  - **Finding-Level F1-Score:** **82.4%**.
  - **Sample-Level Verdict Accuracy:** **100.0%** ($5 / 5$ sample pull requests assigned appropriate review verdicts).
  - **Clean-PR False Positive Rate:** `0.0% observed on sample-clean-pr (0 / 1); broader false positive rate is NOT MEASURABLE due to sample size (N=1)`.
- **Function Calling Verification Status:** `TEST VERIFIED / IMPLEMENTATION VERIFIED`. The two-phase investigation loop is fully implemented and tested with mocked SDK responses in `test_two_phase_agent.py`. Live model traces are not recorded in the repository.
- **Measured Latency:** In-memory fallback engine latency averages **$0.40\text{ ms}$**; end-to-end FastAPI TestClient endpoint latency averages **$2.73\text{ ms}$**.

```
========================================================================================
                      DIFFGUARD VERIFIED SCORECARD (GROUNDED EVIDENCE)
========================================================================================
  Overall Demo Readiness        : A — DEMO READY (For Practical Technical Demonstration)
  Backend Test Suite            : 85 / 85 PASSED (TEST VERIFIED, 100% offline mocks)
  Frontend Test Suite           : 5 / 5 PASSED (TEST VERIFIED, node --test)
  Frontend Stack                : Next.js 15.5.29 / React 19.0.0 (package.json verified)
  Fallback Finding Precision    : 100.0% (7 / 7 observed findings matched real defects)
  Fallback Finding Recall       : 70.0% (7 / 10 ground-truth defects detected)
  Fallback Finding F1-Score     : 82.4%
  Sample-Level Verdict Accuracy : 100.0% (5 / 5 samples assigned correct triage status)
  Clean-PR False Alarm Count    : 0 on sample-clean-pr (General FPR: NOT MEASURABLE)
  Location Validation           : 100.0% of observed findings verified or file-level
  Measured Engine Latency       : 0.40 ms (In-memory) | 2.73 ms (FastAPI HTTP endpoint)
  Live Gemini Function Traces   : NOT VERIFIED (No live traces stored; verified via unit tests)
========================================================================================
```

---

## 2. Evaluation Methodology & Ground-Truth Dataset

Evaluation was conducted against the 5 bundled pull request fixtures in [sample_diffs.py](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/samples/sample_diffs.py).

### Evidence Classification Standards
To maintain evidence integrity, all statements in this audit adhere to strict labels:
* **EXECUTION VERIFIED:** Directly measured or observed in an execution run or benchmark.
* **TEST VERIFIED:** Asserted and verified by an automated test in the repository test suite.
* **IMPLEMENTATION VERIFIED:** Confirmed by inspection of application source code.
* **NOT VERIFIED:** No execution log or verifiable trace exists in the repository.
* **NOT MEASURABLE:** Denominator or sample size is insufficient to support a statistical calculation.

### Ground-Truth Catalog & Defect Inventory

| Sample ID | Files & Churn | Genuinely Present Defects (Ground Truth) | Deterministic Fallback Result | Detection Status |
| :--- | :--- | :--- | :--- | :--- |
| `sample-sqli-auth` | 1 file<br>(+10, -3) | 1. Raw SQLi via f-string (`services/auth_service.py:24`)<br>2. Hardcoded secret `JWT_SECRET_KEY`<br>3. Untested production code (+10 additions, 0 tests) | - SQLi detected (`CWE-89`, line 24)<br>- Test gap detected (file-level)<br>- `JWT_SECRET_KEY` missed by regex | **2 TP / 1 FN**<br>Verdict: `CRITICAL_BLOCKER` |
| `sample-logic-async-bug` | 2 files<br>(+8, -3) | 1. Loop index out-of-bounds in `payments/processor.py:43`<br>2. Missing `await` in `payments/webhook.ts:19` | - Off-by-one loop detected (line 43)<br>- Unawaited custom call missed | **1 TP / 1 FN**<br>Verdict: `CRITICAL_BLOCKER` |
| `sample-resource-leak` | 1 file<br>(+9, -2) | 1. Unclosed `open()` descriptor in `analytics/export_worker.py:27`<br>2. Multi-line `except Exception:\n pass`<br>3. Untested production code (+9 additions, 0 tests) | - Unclosed file detected (line 27)<br>- Test gap detected (file-level)<br>- Multi-line bare except missed | **2 TP / 1 FN**<br>Verdict: `CHANGES_REQUESTED` |
| `sample-untested-complexity` | 1 file<br>(+29, -0) | 1. High cyclomatic complexity (score 11, depth 5)<br>2. Untested production code (+29 additions, 0 tests) | - Complexity warning flagged<br>- Test gap detected (file-level) | **2 TP / 0 FN**<br>Verdict: `CHANGES_REQUESTED` |
| `sample-clean-pr` | 2 files<br>(+41, -0) | *Clean change: In-memory rate limiter with complete unit test suite.* | - 0 findings returned | **1 TN (Sample Level)**<br>Verdict: `APPROVED` |

*Note on Command Injection and Deserialization:* The previous audit mistakenly counted command injection and deserialization in the ground-truth sample catalog. Those rules (`SEC-CMD-003` and `SEC-DESER-004`) exist in [security_scanner.py](file:///C:/Users/HP/OneDrive/Documents/Diffguard/backend/app/tools/security_scanner.py) and are covered by synthetic snippet unit tests in `test_tools.py`, but they are **not** present in the 5 sample PR fixtures.

---

## 3. Detection Accuracy & Failure Mode Breakdown

### 3.1 Security Vulnerabilities (`SECURITY_AND_RELIABILITY`)
* **SQL Injection (`CWE-89`):** `EXECUTION VERIFIED`. Rule `SEC-SQLI-001` detects the raw f-string SQL query in `sample-sqli-auth` at line 24.
* **Hardcoded Secret (`CWE-798`):** `IMPLEMENTATION VERIFIED / LIMITATION`. Rule `SEC-SECRET-002` searches for variable names matching `(jwt[_-]?secret)` immediately followed by `[:=]`. In `sample-sqli-auth`, the variable is named `JWT_SECRET_KEY`. Because of the `_KEY` suffix, the rigid regex pattern fails to flag this secret in fallback mode. In live agent mode, semantic LLM analysis is required to identify this credential.
* **Resource Leaks (`CWE-775`):** `EXECUTION VERIFIED`. Detected by hunk pattern matching in `fallback_engine.py:163` (`= open(` without `with`), correctly locating `analytics/export_worker.py:27`.

### 3.2 Logic & Semantic Bugs (`BUG_OR_LOGIC_ERROR`)
* **Off-by-One Loop Boundary:** `EXECUTION VERIFIED`. Captured by `range(len(...) + 1)` pattern matching in `fallback_engine.py:189` on line 43 of `payments/processor.py`.
* **Unhandled Async Promises:** `IMPLEMENTATION VERIFIED / LIMITATION`. The static regex in `syntax_checker.py:78` only matches known library prefixes (`fetch`, `axios`, `prisma`). Because the webhook calls a custom function `recordSuccessfulPayment()`, the deterministic syntax checker fails to detect the missing `await`.

### 3.3 Exception Silencing
* **Multi-Line Bare Except:** `IMPLEMENTATION VERIFIED / LIMITATION`. In `sample-resource-leak`, `except Exception:` and `pass` are on separate lines. Because `syntax_checker.py:45` applies a single-line regex (`re.search(r"except\s+Exception\s*:\s*pass", line)`), it fails to detect the exception suppression.

### 3.4 Code Complexity & Test Coverage
* **Complexity Metrics:** `EXECUTION VERIFIED`. `complexity_analyzer.py` calculates cyclomatic complexity $= 11$ and nesting depth $= 5$ on `calculate_tiered_rebate`, generating a file-level maintainability warning.
* **Test Gap Analyzer:** `EXECUTION VERIFIED`. `test_requirement_analyzer.py` triggers when production additions $\ge 8$ and test files $= 0$, successfully flagging `sample-sqli-auth`, `sample-resource-leak`, and `sample-untested-complexity`. It correctly recognizes `tests/test_rate_limiter.py` in `sample-clean-pr` and emits no warning.

---

## 4. False-Positive Analysis & Clean-Code Handling

* **Observed Clean-PR Behavior:** `EXECUTION VERIFIED`. Evaluated against `sample-clean-pr`:
  * Security Findings: 0
  * Syntax Findings: 0
  * Complexity Warnings: 0
  * Test Coverage Warnings: 0
  * Overall Findings: 0. Verdict: `APPROVED`.
* **Statistical Limitation:** Observing 0 false alarms on a single clean sample ($N=1$) confirms that the rules do not fire indiscriminately on this well-engineered token bucket implementation. However, calculating a broader "0.0% false-positive rate across software engineering" is statistically invalid without a large-scale repository benchmark.
* **Metric Classification:** `NOT MEASURABLE (General FPR) — INSUFFICIENT VERIFIED EVIDENCE`.

---

## 5. Recalculated Evaluation Metrics (Ground-Truth Basis)

All previously reported metrics (94.1% accuracy, 93.8% precision, 91.7% recall, 16/17 assertions) were derived from arbitrary assertion tallies rather than ground-truth defect counts. They have been replaced with defensible calculations:

### Ground-Truth Evaluation Matrix (Fallback Engine on 5 Curated Samples)

```
                              GROUND TRUTH DEFECTS
                             Present         Absent
                      +-----------------+-----------------+
         Reported     |     TP = 7      |     FP = 0      |
FINDINGS              +-----------------+-----------------+
         Not Reported |     FN = 3      |  TN = Undefined*|
                      +-----------------+-----------------+
```
*\*Note: True negatives at the finding level cannot be counted because the number of non-existent defects that were not reported is theoretically unbounded.*

### Defensible Finding-Level Metrics
* **Finding Precision:**
  $$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{7}{7 + 0} = 100.0\% \quad (7/7)$$
* **Finding Recall:**
  $$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{7}{7 + 3} = 70.0\% \quad (7/10)$$
* **Finding F1-Score:**
  $$F_1 = 2 \times \frac{1.0 \times 0.70}{1.0 + 0.70} = 82.4\%$$
* **Sample-Level Triage Accuracy:**
  $$\text{Accuracy}_{\text{sample}} = \frac{\text{Correct Sample Verdicts}}{\text{Total Samples}} = \frac{5}{5} = 100.0\%$$
* **Overall Statistical Accuracy:** `NOT MEASURABLE AT FINDING LEVEL (Undefined TN Denominator)`.

---

## 6. Gemini Function Calling & Two-Phase Loop Verification

### Evidence Trace Status Table

| Step | Claimed Behavior | Evidence Type | Verification Finding |
| :--- | :--- | :--- | :--- |
| **1. Tool Declarations** | Strict `types.Tool` schemas passed to Gemini | `TEST VERIFIED` | Verified in `test_tool_dispatcher.py` and `test_two_phase_agent.py`. |
| **2. Model Function Call** | Gemini requests `inspect_diff_hunk` | `TEST VERIFIED` | Verified via mocked SDK response in `test_two_phase_agent.py`. Live model traces are `NOT VERIFIED`. |
| **3. Dispatcher Execution** | Tool executes within in-memory limits | `TEST VERIFIED` | `tool_dispatcher.py` bounds output, caches duplicates, and tracks attempts. |
| **4. Tool Response Loop** | Function response returned in conversation | `TEST VERIFIED` | Role `"user"` with `function_response` part verified in call kwargs. |
| **5. Investigation Cap** | Max 3 turns, max 6 tool calls enforced | `TEST VERIFIED` | Tested in `test_maximum_investigation_turns_enforcement`. |
| **6. Phase B Synthesis** | Structured JSON synthesis with tools disabled | `TEST VERIFIED` | Verified `tools=None` and `response_schema=ReviewResponse` in synthesis call. |
| **7. Live Trace Evidence** | Actual model traces from live API calls | `NOT VERIFIED` | No live model conversation logs or traces are persisted in the repository. |

### Cautionary Corrections
* **"100% Guaranteed Schema Compliance":** `CORRECTED`. While Gemini structured output (`response_schema`) and Pydantic validation significantly reduce malformations, network interruptions or provider errors can still result in invalid responses, which the agent handles by falling back to the heuristic engine.
* **"Absolute Line-Coordinate Grounding":** `CORRECTED`. Function calling allows the model to inspect patch lines, but location validation remains the deterministic layer that verifies coordinate bounds.

---

## 7. Fallback Engine Reliability & Measured Latency

### Reliability Verification
* **Fallback Triggering:** `TEST VERIFIED`. Unit tests in `test_two_phase_agent.py` confirm fallback activates on investigation exception, synthesis failure, timeout expiration, or invalid response.
* **"Zero Downtime" Claim:** `CORRECTED`. If an unexpected exception occurs inside `run_heuristic_code_review()` or the unidiff parser, it propagates as HTTP 500. The engine is resilient, but claims of absolute zero downtime are unverified.

### Actual Measured Latencies (Empirically Benchmarked)
Measured on the local test harness (50 iterations per sample):
* **In-Memory Fallback Engine:**
  * `sample-sqli-auth`: $0.35\text{ ms}$ (min: $0.31\text{ ms}$, max: $0.61\text{ ms}$)
  * `sample-logic-async-bug`: $0.32\text{ ms}$ (min: $0.29\text{ ms}$, max: $0.47\text{ ms}$)
  * `sample-resource-leak`: $0.22\text{ ms}$ (min: $0.19\text{ ms}$, max: $0.33\text{ ms}$)
  * `sample-untested-complexity`: $0.41\text{ ms}$ (min: $0.37\text{ ms}$, max: $0.54\text{ ms}$)
  * `sample-clean-pr`: $0.69\text{ ms}$ (min: $0.65\text{ ms}$, max: $0.91\text{ ms}$)
  * **Overall Average:** **$0.40\text{ ms}$**
* **End-to-End FastAPI TestClient Endpoint:**
  * Average: **$2.73\text{ ms}$** (min: $2.28\text{ ms}$, max: $3.90\text{ ms}$)
* *Historical Claim Correction:* The previously reported "12–28 ms" range was an unverified estimate; actual measured latency is significantly faster ($< 3\text{ ms}$ total HTTP round-trip).

---

## 8. Timeout and Cancellation Governance

Following the Phase 2.2.3 independent verification, timeout behavior is strictly characterized as follows:

> **Verified Implementation Statement:**  
> The agent applies a cooperative monotonic deadline ($60.0\text{ s}$) and bounded provider transport timeouts (`GEMINI_REQUEST_TIMEOUT_MS = 25_000`). Because the synchronous provider call (`active_client.models.generate_content`) cannot be forcibly interrupted while blocked in an underlying socket read, cancellation may not be instantaneous. The transport timeout bounds socket inactivity, but does not constitute a strict end-to-end execution ceiling.

---

## 9. Location Validation & Evidence Integrity

### Verified Classification
Across the 7 findings generated by the fallback engine:
* **Verified Lines ($3$ findings):**
  * `services/auth_service.py:24` $\rightarrow$ `LocationStatus.VERIFIED` (`LineSide.NEW`)
  * `payments/processor.py:43` $\rightarrow$ `LocationStatus.VERIFIED` (`LineSide.BOTH`)
  * `analytics/export_worker.py:27` $\rightarrow$ `LocationStatus.VERIFIED` (`LineSide.NEW`)
* **File-Level Scopes ($4$ findings):**
  * Test gaps and complexity warnings correctly assigned `LocationStatus.FILE_LEVEL` (`LineSide.FILE_LEVEL`).
* **Line Clamping:** **0 line numbers clamped.** Out-of-hunk lines preserve their reported coordinate and receive `LocationStatus.UNVERIFIED`.
* *Historical Claim Correction:* The previous claim of "12/12 findings" conflated unit test assertions in `test_finding_integrity.py` with findings from the sample PR evaluation.

---

## 10. Automated Test & Build Verification

* **Backend Test Suite:** `TEST VERIFIED`
  * Command: `python -m pytest backend/tests -v`
  * Execution Result: **85 passed** in 46.29s (0 failed, 0 skipped).
  * Scope: All 85 tests run offline using mocks for Gemini API interactions.
* **Frontend Test Suite:** `TEST VERIFIED`
  * Command: `npm test --prefix frontend`
  * Execution Result: **5 passed** in 103ms (0 failed, 0 skipped).
* **Frontend Production Build:** `TEST VERIFIED`
  * Command: `npm run build --prefix frontend`
  * Execution Result: Compiled successfully in 3.2s with 0 errors.
  * Verified Dependencies: **Next.js 15.5.29**, **React 19.0.0**, Tailwind CSS 3.4.16.

---

## 11. Reassessed Scorecard

| Evaluation Area | Evidence Type | Verified Result | Stated Limitations |
| :--- | :--- | :--- | :--- |
| **Security Detection** | `EXECUTION VERIFIED` | SQLi and file descriptor leaks detected. | Misses `JWT_SECRET_KEY` due to regex identifier boundary. |
| **Logic Bug Detection** | `EXECUTION VERIFIED` | Off-by-one array index error detected. | Misses custom async unawaited calls in static checker. |
| **Complexity Analysis** | `EXECUTION VERIFIED` | Cyclomatic score 11, nesting depth 5 flagged. | Evaluates additions only; does not analyze unchanged context. |
| **Test Gap Analyzer** | `EXECUTION VERIFIED` | 3 production test gaps flagged; clean PR passed. | Threshold-based ($\ge 8$ additions); does not evaluate test quality. |
| **Clean PR Behavior** | `EXECUTION VERIFIED` | 0 findings on `sample-clean-pr`. | $N=1$ sample; broader FPR is `NOT MEASURABLE`. |
| **Location Validation** | `TEST & EXECUTION VERIFIED` | 100% of findings accurately mapped; 0 clamped. | Validates patch coordinate presence, not semantic bug truth. |
| **Function Calling** | `TEST VERIFIED` | 2-phase loop, tool limits, and schemas tested. | Verified via mocked SDK unit tests; no live API traces logged. |
| **Fallback Engine** | `EXECUTION VERIFIED` | Evaluates diffs in 0.40 ms (engine) / 2.73 ms (HTTP). | Unhandled exceptions propagate as HTTP 500 (not zero-downtime). |
| **SSE Progress Stages** | `TEST VERIFIED` | 5 stage transitions emitted over SSE stream. | Verified in unit tests and frontend component contracts. |
| **Frontend Navigation** | `TEST VERIFIED` | Line keys `${side}-${lineNo}` prevent collisions. | Verified by 5 automated tests in `diff_viewer_logic.test.mjs`. |

---

## 12. Recommended 3-Scenario Demo Sequence

This 3-scenario sequence remains fully supported by verified application behavior:
1. **Scenario 1 (Security Blocker):** `sample-sqli-auth` $\rightarrow$ Demonstrates raw SQL injection detection, `CRITICAL_BLOCKER` triage, and jumping directly to line 24 in the DiffViewer.
2. **Scenario 2 (Multi-File Logic Error):** `sample-logic-async-bug` $\rightarrow$ Demonstrates multi-file diff parsing, array out-of-bounds detection on line 43, and SSE stage progression.
3. **Scenario 3 (Clean Production PR):** `sample-clean-pr` $\rightarrow$ Demonstrates false-positive resistance, detection of test files, and an `APPROVED` review verdict.

---

## 13. Audit Sign-Off

* **Audit Verdict:** **A — DEMO READY (With Stated Evidence Limitations)**
* **Repository Commit:** `5993e7fa6e20ec71c63d9ab4b41db3feaf25f842`
* **Audited Document:** [DIFFGUARD_EVALUATION_AND_DEMO_READINESS_AUDIT.md](file:///C:/Users/HP/OneDrive/Documents/Diffguard/docs/audits/DIFFGUARD_EVALUATION_AND_DEMO_READINESS_AUDIT.md)
* **Supplementary Report:** [DIFFGUARD_EVALUATION_EVIDENCE_INTEGRITY_AUDIT.md](file:///C:/Users/HP/OneDrive/Documents/Diffguard/docs/audits/DIFFGUARD_EVALUATION_EVIDENCE_INTEGRITY_AUDIT.md)
