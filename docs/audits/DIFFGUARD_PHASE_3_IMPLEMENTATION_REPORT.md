# DiffGuard — Phase 3 Implementation Report
## Configurable Engineering Standards Engine (MVP)
### Repository-Specific Policy Enforcement, Deterministic Evaluation & Review Pipeline Integration

**Project:** DiffGuard — AI-Powered Git Diff & Pull Request Review Agent  
**Repository:** `C:\Users\HP\OneDrive\Documents\Diffguard`  
**Phase:** 3 — Configurable Engineering Standards Engine (MVP)  
**Baseline Git Commit:** `5993e7fa6e20ec71c63d9ab4b41db3feaf25f842`  
**Status:** COMPLETE & VERIFIED  
**Date:** November 14, 2026  
**Backend Test Suite:** 112 / 112 passed (100%)  
**Frontend Test Suite:** 8 / 8 passed (100%)  
**Frontend Production Build:** Successful (Next.js 15.5.29)  

---

## 1. Executive Summary

Phase 3 introduces a deterministic, repository-specific **Engineering Standards Engine** to DiffGuard. Prior to this phase, DiffGuard evaluated diffs exclusively for general software defects, security risks, syntax errors, and missing test coverage using hardcoded heuristics and Gemini-driven multi-turn investigation.

With Phase 3, development teams can define custom repository engineering standards in `.diffguard.yaml`. The engine deterministically parses and evaluates patch modifications against five core engineering policies:
1. **Maximum Function Length** (`code_style.max_function_length`)
2. **Maximum Nesting Depth** (`code_style.max_nesting_depth`)
3. **Prohibited Imports / Modules** (`security.prohibited_imports`)
4. **Custom Regex Anti-Patterns** (`security.custom_patterns`)
5. **Mandatory Test Changes** (`testing.require_test_changes`)

Crucially, Phase 3 establishes an immutable architectural taxonomy:
- **Defects (`code_defect`):** True software bugs, vulnerabilities, logic errors, or syntax crashes.
- **Policy Violations (`policy_violation`):** Breaches of repository-configured style, organizational, or architectural standards.
- **Recommendations (`recommendation`):** Non-blocking DX, readability, or optimization suggestions.

Policy violations are **never** reported as code defects. The deterministic evaluation results are preserved with verified location references, merged into both the Gemini reasoning prompt and final review response, and surfaced distinctly across the backend API and Next.js frontend UI.

---

## 2. Architectural Design & Component Topology

```
                     +---------------------------------------+
                     |           ReviewRequest               |
                     | (diff_content, standards_yaml, ...)   |
                     +-------------------+-------------------+
                                         |
                                         v
                    +-----------------------------------------+
                    | Stage 1: Ingestion & Schema Validation  |
                    | parse_standards_config() [Safe YAML]    |
                    +--------------------+--------------------+
                                         |
                                         v
                    +-----------------------------------------+
                    | Stage 2: Unified Diff Decomposition     |
                    | parse_diff() -> ParsedDiff              |
                    +--------------------+--------------------+
                                         |
                                         v
       +---------------------------------+---------------------------------+
       |                                                                   |
       v                                                                   v
+-------------------------------+                       +----------------------------------+
| Stage 3: Static Analysis      |                       | Stage 3: Engineering Standards   |
| - Security Scanner            |                       |          Rule Engine             |
| - Complexity Analyzer         |                       | - max_function_length            |
| - Syntax/Linter Checker       |                       | - max_nesting_depth              |
| - Test Requirement Analyzer   |                       | - prohibited_imports             |
+---------------+---------------+                       | - custom_patterns                |
                |                                       | - require_test_changes           |
                |                                       +-----------------+----------------+
                |                                                         |
                +------------------------+--------------------------------+
                                         | (Deterministic Policy Findings)
                                         v
                     +---------------------------------------+
                     | Stage 4: AI Agent Reasoning Loop      |
                     | Gemini 2-Phase or Heuristic Fallback  |
                     | (Standards summary injected in prompt)|
                     +-------------------+-------------------+
                                         |
                                         v
                     +---------------------------------------+
                     | Stage 5: Synthesis & Location Verif.  |
                     | - Deterministic Merge of Policy Rules |
                     | - validate_all_findings(findings)     |
                     | - Partition Metrics: Defects vs Rules |
                     +-------------------+-------------------+
                                         |
                                         v
                              +--------------------+
                              |   ReviewResponse   |
                              +--------------------+
```

---

## 3. Configuration Schema & Validation Safeguards

The configuration schema is strictly defined using Pydantic v2 in `backend/app/standards/config_schema.py`:

### Key Specifications:
- **Root Model:** `EngineeringStandardsConfig` with `version: int = 1`, optional `project` metadata, and `standards: StandardsPolicies`.
- **Strict Key Validation:** `extra = "forbid"` enforces that unexpected or misspelled keys raise immediate validation errors rather than silently passing.
- **File Size Ceiling:** Maximum allowable configuration length is strictly capped at **64 KB** (`MAX_CONFIG_SIZE_BYTES = 65536`). Oversized configurations are rejected upfront.
- **Rule ID Sanitization:** Must conform to `^[A-Za-z0-9_-]{2,64}$`.
- **Regex Safety:** Custom regex patterns are capped at **500 characters** and pre-compiled on schema ingestion with `re.compile()`. Invalid regular expressions raise a clear 400 validation error before any execution takes place.
- **Safe Parsing:** Uses `yaml.safe_load(yaml_str)`. Python `pickle`, object deserialization, or script execution is strictly prevented.
- **Case-Insensitive Severity:** Uses a Pydantic `BeforeValidator` to accept `low`, `LOW`, `medium`, `HIGH`, etc., normalizing seamlessly into `SeverityLevel`.

---

## 4. Deterministic Rule Evaluators

The evaluation engine resides in `backend/app/standards/rule_engine.py` and delegates to five modular rule evaluators in `backend/app/standards/rules/`:

| Rule Name | File Path | Language Support | Mechanism & Context Handling |
|:---|:---|:---|:---|
| **Max Function Length** | `rules/function_length.py` | Python, JS, TS | Scans unified diff hunks for function signatures. Computes line count strictly for functions whose body closes inside the hunk. If a function is truncated or context is incomplete, it is **not flagged** (`not_evaluated` state) to prevent hallucinated line counts. |
| **Max Nesting Depth** | `rules/nesting_depth.py` | Python, JS, TS, Generic | Analyzes indentation levels and brace nesting on added (`+`) lines only. Ignores comments and blank lines. Emits exact line numbers. |
| **Prohibited Imports** | `rules/prohibited_imports.py` | Python, JS, TS | Regex-matches prohibited module imports (`import x`, `from x import y`, `require('x')`). Evaluates **only added lines**; deleted lines (`-`) removing prohibited imports are never penalized. |
| **Custom Anti-Patterns** | `rules/custom_patterns.py` | Universal (all files) | Matches user-defined pre-compiled regular expressions against added lines. Associates findings with exact line numbers, custom rule IDs, and custom warning messages. Deduplicates matches per line. |
| **Mandatory Test Changes** | `rules/test_requirements.py` | Universal | Detects whether non-test production code files are modified without corresponding additions in test files. **Advisory Patch Limitation:** Clearly notes in `validation_note` that tests may exist outside the patch, avoiding unverified repository-wide claims. |

---

## 5. Finding Taxonomy & Separation

All findings adhere to the enhanced `Finding` schema in `backend/app/models/schemas.py`:

```python
class FindingType(str, Enum):
    CODE_DEFECT = "code_defect"
    POLICY_VIOLATION = "policy_violation"
    RECOMMENDATION = "recommendation"

class PolicyEvaluationStatus(str, Enum):
    VIOLATED = "violated"
    PASSED = "passed"
    NOT_EVALUATED = "not_evaluated"
```

### Metrics Partitioning in `ReviewSummary`:
```json
{
  "total_findings": 3,
  "total_defects": 1,
  "total_policy_violations": 2,
  "total_recommendations": 0,
  "by_finding_type": {
    "code_defect": 1,
    "policy_violation": 2,
    "recommendation": 0
  }
}
```
The relationship `total_findings == total_defects + total_policy_violations + total_recommendations` is strictly maintained and asserted in test suites.

---

## 6. Review Pipeline & Fallback Engine Integration

### ReviewAgent Integration (`backend/app/agent/reviewer_agent.py`):
1. **Stage 1 (Ingestion):** If `request.standards_yaml` is provided, parses it via `parse_standards_config()`. Any YAML syntax error or schema violation raises an HTTP 400 error immediately.
2. **Stage 3 (Evaluation):** If standards are enabled, executes `EngineeringStandardsEngine.evaluate_standards(parsed_diff)`. Emits stage details with the active rule evaluation count.
3. **Stage 4 (Synthesis):**
   - Injects the active standards summary into `DIFFGUARD_SYSTEM_INSTRUCTION` and user prompt.
   - **Deterministic Preservation:** All deterministic policy findings are merged into the final list. Even if the Gemini model ignores or truncates a policy violation in its response, the agent deterministically restores it.
4. **Fallback Engine (`backend/app/agent/fallback_engine.py`):**
   - `run_heuristic_code_review` accepts `policy_findings`.
   - Merges, deduplicates, and runs location validation (`validate_all_findings`) across both heuristic defects and policy violations.

---

## 7. Frontend Integration

The Next.js 15.5.29 / React 19 frontend was extended to provide first-class visibility into standards configuration and enforcement:

1. **`DiffInput.tsx`:**
   - Added collapsible **Engineering Standards Policy (.diffguard.yaml)** accordion.
   - Includes full YAML editor textarea, "Load Sample Policy" button, and "Clear" button.
   - Live status indicator: Displays active policy line count or "Default Policies Active".
2. **`FindingCard.tsx`:**
   - Distinct badges for finding types:
     - **Defects:** Rose badge (`Defect`, bug icon).
     - **Policy Violations:** Violet badge (`Policy Violation`, sliders icon).
     - **Recommendations:** Teal badge (`Recommendation`, lightbulb icon).
   - Prominently displays rule tag `[RULE-ID]` (e.g. `[POLICY-AUTH-001]`), rule name, and policy category.
   - Dedicated policy banner detailing the standard enforced and evaluation status.
3. **`FindingsList.tsx`:**
   - Interactive type filter tabs: **All Findings**, **Defects**, **Policy Violations**, and **Recommendations** with live counter pills.
   - Search bar searches title, file path, description, `rule_id`, `rule_name`, and `policy_category`.
   - Export report includes finding types and rule metadata.
4. **`SummaryCards.tsx`:**
   - Dedicated metric cards for **Software Defects** (rose) and **Policy Violations** (violet).
   - High/critical blocker counters and confidence distribution.
5. **`app/page.tsx`:**
   - Binds `standardsYaml` state to the API payload across streaming (`/api/review/stream`) and synchronous (`/api/review`) flows.

---

## 8. Verification & Test Evidence Matrix

### 8.1 Backend Test Results (`pytest`)
All 112 tests across 16 test modules pass with zero failures:

| Test Module | Tests | Status | Scope Tested |
|:---|:---:|:---:|:---|
| `test_standards_config.py` | 12 | PASS | YAML parsing, default config, unknown keys rejection, malformed syntax, non-dict root, invalid severity, regex length limits, numeric bounds |
| `test_standards_engine.py` | 8 | PASS | Function length, nesting depth, prohibited imports, deleted lines immunity, incomplete context handling, custom regex patterns, test change requirements |
| `test_standards_pipeline.py` | 7 | PASS | REST endpoints (`/api/standards/default`, `/api/standards/validate`), `/api/review` standards evaluation, separation of defects vs policies, deterministic Gemini merge |
| `test_agent_schema.py` | 3 | PASS | Schema validation and heuristic fallback |
| `test_api_routes.py` | 7 | PASS | Sample diff endpoints, health check, review routes |
| `test_diff_parser.py` | 6 | PASS | Multi-file unified diff parsing |
| `test_finding_integrity.py` | 11 | PASS | Location verification, line clamping prevention |
| `test_security_adversarial.py` | 2 | PASS | Prompt injection boundary isolation |
| `test_security_hardening.py` | 13 | PASS | CORS configuration and error sanitization |
| `test_tool_dispatcher.py` | 17 | PASS | Tool call budget, parameter validation, caching |
| `test_tools.py` | 8 | PASS | Deterministic analyzers (SQLi, secrets, syntax) |
| `test_two_phase_agent.py` | 18 | PASS | Investigation loop, cancellation, timeout handling |
| **Total Backend Tests** | **112** | **PASS** | **100% Pass Rate** |

### 8.2 Frontend Test Results (`node --test`)
| Test Module | Tests | Status | Scope Tested |
|:---|:---:|:---:|:---|
| `diff_viewer_logic.test.mjs` | 5 | PASS | Normalization, old/new line side anchoring, navigation highlighting |
| `standards_filtering_logic.test.mjs` | 3 | PASS | Finding count partitioning (defects vs policies vs recommendations), type filtering, rule-based search matching |
| **Total Frontend Tests** | **8** | **PASS** | **100% Pass Rate** |

### 8.3 Frontend Build Verification
- Command: `npm run build --prefix frontend`
- Result: **Compiled successfully in 2.9s**
- Static optimization: **4 / 4 pages generated without errors or type warnings**

---

## 9. Backward Compatibility Verification

Zero-configuration diff reviews continue to function with complete backward compatibility:
1. When `ReviewRequest.standards_yaml` is `None` or omitted:
   - `get_default_standards_config()` returns a valid configuration with rules set to `enabled: false`.
   - No unexpected policy violations are introduced into existing reviews or legacy test fixtures.
2. Legacy finding structures lacking `finding_type` automatically default to `FindingType.CODE_DEFECT`.
3. Location validation pipeline and existing heuristic analyzers run completely unaffected.

---

## 10. Conclusion & Readiness Verdict

**VERDICT: PRODUCTION READY (MVP)**

Phase 3 delivers a robust, secure, deterministic Engineering Standards Engine that bridges the gap between general AI diff analysis and team-specific code governance. The engine safely parses configuration, deterministically evaluates rules on patch additions, clearly separates defects from policy violations, and seamlessly integrates with both the backend pipeline and Next.js frontend.

