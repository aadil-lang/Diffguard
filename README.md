# DiffGuard — AI-Powered Git Diff & Pull Request Review Agent

> **FLEXGCC AI Engineer Practical Assignment Submission**  
> An autonomous agent that analyzes Git diffs and produces structured, actionable review feedback on potential bugs, security vulnerabilities, missing tests, and engineering standards compliance.

---

## A. Project Overview

Code reviews are a critical safeguard in software engineering, but human reviewers frequently miss subtle regressions, edge cases, and security vulnerabilities under time pressure. 

**DiffGuard** is a specialized AI review agent designed to inspect Git unified diffs before code merges. Unlike generic conversational chatbots, DiffGuard operates as a structured, two-phase agent:
1. **Investigation Phase**: Autonomously inspects code hunks and surrounding patch context using specialized tools while gathering deterministic static analysis signals.
2. **Synthesis Phase**: Cross-references findings, checks against configurable engineering standards, validates line locations against actual diff hunks, and emits schema-validated review reports with actionable remediations.

If external AI providers are unavailable, DiffGuard gracefully falls back to an internal deterministic heuristic engine, guaranteeing zero-failure availability.

---

## B. Functionality

- **Resilient Diff Ingestion**: Parses multi-file, multi-hunk unified diffs with automated header healing for malformed patches.
- **Structured Findings**: Emits standardized finding objects including file path, line number, diff side (`OLD`/`NEW`), severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`), category, CWE classification, title, description, and copyable remediation code.
- **Multi-Category Defect Detection**:
  - *Security Risks*: SQL injection, hardcoded credentials, OS command injection, path traversal.
  - *Syntax & Runtime Defects*: Python bare `except`, JavaScript loose equality (`==`), resource leaks, unhandled promises.
  - *Code Maintainability*: Cyclomatic complexity spikes, deep nesting depth (>3 levels).
  - *Missing Test Coverage*: AST-based test gap analysis flagging modified production logic lacking corresponding test additions.
- **Agent Tool Calling**: The agent dynamically invokes specialized tools (`inspect_diff_hunk`, `inspect_patch_context`) within strict token and turn budgets to clarify changes before finalizing review findings.
- **Configurable Engineering Standards**: Enforces repository-level policies (file size, function line length, naming conventions, docstrings, forbidden imports) via `standards.yaml`.
- **Interactive Web Dashboard**: Built with Next.js 15 and Tailwind CSS, featuring side-by-side / unified diff viewing, side-aware finding badges, severity filtering, sample diff selection, and real-time SSE progress streaming.
- **Deterministic Heuristic Fallback**: An offline analysis engine that generates immediate reviews when Gemini API keys are omitted or external services are unreachable.

---

## C. Implementation Details

DiffGuard is built with modern, production-grade frameworks:

- **Backend Architecture**:
  - **Framework**: FastAPI (>=0.115.0) on Python 3.12 with Uvicorn (>=0.30.0).
  - **Data Contracts**: Pydantic v2 (>=2.8.0) and Pydantic-Settings (>=2.4.0) for strict type validation.
  - **AI Integration**: Google GenAI SDK (`google-genai` >=1.0.0) targeting `gemini-2.5-flash` with function calling and structured response schemas.
  - **Streaming**: Server-Sent Events via `sse-starlette` (>=2.1.0) streaming granular execution stages to the frontend.
  - **Static Analysis**: `unidiff` (>=1.0.1) for diff parsing, Python `ast` for syntax/complexity inspection, and regular expression engines (`re`, `google-re2`).
  - **Testing**: `pytest` (>=8.0.0) with **251 unit and regression tests** (100% pass rate).
- **Frontend Architecture**:
  - **Framework**: Next.js (15.1.0) with React (19.0.0) App Router.
  - **Styling & UI**: Tailwind CSS (3.4.16) and Lucide React icons (0.469.0).
  - **Testing**: Node.js built-in test runner with **8 frontend tests** (100% pass rate).

---

## D. What Went Wrong & How It Was Handled

Developing an autonomous agent with external LLM boundaries revealed several real-world engineering hurdles:

1. **Hallucinatory Finding Locations**:
   - *Problem*: Early LLM evaluations occasionally emitted findings referencing non-existent line numbers or lines outside the modified diff hunks.
   - *Solution*: Built a deterministic `location_validator.py` that cross-references all candidate findings against parsed diff hunk boundaries. Unmodified or out-of-bounds line numbers are clamped to the nearest hunk line or converted into file-level observations.
2. **Duplicate & Conflicting Findings**:
   - *Problem*: Both static tools and the LLM would flag the same issue with slightly different titles, causing redundant entries.
   - *Solution*: Implemented canonical path normalization and side-aware finding deduplication (`OLD` line vs `NEW` line), merging static rule attributions into unified authoritative findings.
3. **Agent Loop Budget Exhaustion**:
   - *Problem*: Complex diffs risked triggering repeated tool invocations, threatening latency deadlines and API quotas.
   - *Solution*: Enforced a 30-second monotonic deadline, a maximum of 3 investigation turns, a 10-call tool budget, and invocation caching in `ToolDispatcher`.
4. **Secret Disclosure Across Boundaries**:
   - *Problem*: Adversarial security audits revealed that raw credentials in diffs could pass into LLM prompts, AST parser exception strings (`SyntaxError.text`), or error logs.
   - *Solution*: Implemented defense-in-depth sanitization: `sanitize_diff_content()` strips credentials prior to prompt construction, `ContainerScopeTracker` tracks multiline container secrets across diff lines, and AST snippet cleaners protect parser exceptions.
5. **SQL f-String False Positive**:
   - *Problem*: The query `raw_query = f"SELECT ... AND password = '{password_hash}'"` triggered false hardcoded secret findings because `password` appeared near quotes.
   - *Solution*: Implemented `is_index_inside_quote()` to track character quote state up to the identifier, preventing strings inside SQL templates from matching secret assignment rules.
6. **ES6 Backtick Delimiter Gap**:
   - *Problem*: JavaScript backtick credentials (``const API_KEY = `secret`;``) escaped regex checks that only targeted single and double quotes.
   - *Solution*: Unified delimiter patterns with `STRING_LITERAL` supporting single, double, and backtick quotes across all redactors and trackers.

---

## E. Future Improvements

The following items are identified for future production expansion:

- **VCS Platform Webhooks**: Direct GitHub Action and GitLab CI integrations to post comments directly on pull request threads.
- **Multi-Language AST Engines**: Tree-sitter integration for deep syntax inspection across Go, Rust, Java, and C++.
- **Expanded Real-World Evaluation**: Benchmarking agent recommendations against large-scale public pull request datasets.
- **OpenTelemetry Instrumentation**: Distributed tracing for latency profiling across individual tool invocations and LLM turns.
- **End-to-End Browser Automation**: Playwright integration suites for frontend regression testing.

---

## F. Running Locally

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Node.js 18+ (tested on Node.js 22)
- Optional: Google Gemini API key (for live AI mode)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
```

### 3. Environment Configuration (Optional)
DiffGuard runs completely offline via its deterministic fallback engine if no API key is provided. To enable live Gemini agent reasoning:
```bash
# In backend/.env or your terminal:
export GEMINI_API_KEY="your-gemini-api-key"
```

### 4. Starting the Application

**Option A — Automated Launcher (Windows):**
```bash
# In root directory:
start.bat
# Or using PowerShell:
.\start.ps1
```

**Option B — Manual Launch:**
```bash
# Terminal 1 (Backend):
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 (Frontend):
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## G. Running Test Suites

```bash
# Backend pytest suite (251 tests):
python -m pytest backend/tests -v

# Frontend test suite (8 tests):
npm --prefix frontend test
```

---

## H. Production Deployment Commands

### Backend Production Startup
```bash
cd backend
# Set production environment variables
export APP_ENV="production"
export DEBUG="False"
export CORS_ORIGINS="https://your-frontend-domain.com"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend Production Build & Startup
```bash
cd frontend
export NEXT_PUBLIC_API_URL="https://api.your-backend-domain.com"
npm run build
npm run start
```
