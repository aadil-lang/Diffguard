# DiffGuard — Cloud Deployment & Live Gemini Demonstration Script

**Target Duration:** ~3 to 5 minutes  
**Format:** Live Cloud Walkthrough (Vercel Frontend + Render Backend + Google GenAI)  
**Style:** Professional, engineering-focused demonstration  

---

## Walkthrough Sequence

### 1. Introduction & Cloud Architecture (0:00 – 0:40)
- **Visual:** Open deployed DiffGuard URL on Vercel (`https://diffguard.vercel.app`).
- **Narration:**
  > *"Welcome to this live cloud demonstration of DiffGuard. DiffGuard is an AI-powered code review agent designed to analyze Git unified diffs, run deterministic static analyzers, investigate context via dynamic tool calling, and deliver structured review findings.
  >
  > The application is deployed in a zero-monthly-cost split cloud architecture: our Next.js frontend is hosted on Vercel, our FastAPI backend is running on Render, and agent reasoning is powered by Google's Gemini API."*

### 2. Scenario A — Vulnerable Authentication Service (0:40 – 1:30)
- **Visual:** Select `sample-sqli-auth` from the dropdown. Inspect the diff in the viewer.
- **Narration:**
  > *"To demonstrate DiffGuard in action, I’ll select our vulnerable authentication sample. Looking at the diff, we see an added hardcoded JWT secret on line 15, and an SQL query constructed with an unsanitized f-string on line 24.
  >
  > Now I'll click 'Start AI Code Review'. DiffGuard streams real-time progress over Server-Sent Events through diff sanitization, AST parsing, static analysis, agent reasoning, and report synthesis."*

### 3. Review Results & Live Tool Calling Evidence (1:30 – 2:30)
- **Visual:** Review completes. Summary cards show verdict **"Needs Attention"** (Critical Blocker) and engine attribution: `gemini-agent (gemini-3.5-flash-lite) [1 tool call(s)]`.
- **Narration:**
  > *"The review has completed in under 9 seconds. Notice the engine attribution badge: DiffGuard transparently reports that this review was synthesized by Gemini 3.5 Flash-Lite after executing one tool call.
  >
  > During the investigation turn, Gemini autonomously called our allowlisted `inspect_diff_hunk` tool to retrieve the exact hunk bounds before issuing findings.
  >
  > Three structured findings are identified:
  > 1. A Critical SQL Injection vulnerability on line 24 with CWE-89 classification and parameterized remediation.
  > 2. A Critical Hardcoded Secret on line 15, with the credential value safely redacted in the displayed evidence.
  > 3. A Medium finding for missing unit tests.
  >
  > Clicking 'Navigate to diff location' scrolls directly to the verified lines in the diff viewer."*

### 4. Scenario B — Clean Pull Request (2:30 – 3:15)
- **Visual:** Select `sample-clean-pr`. Click "Start AI Code Review".
- **Narration:**
  > *"Next, let's verify how DiffGuard handles good code. I’ll switch to 'sample-clean-pr' — a rate-limiter implementation accompanied by complete unit tests and parameterized queries.
  >
  > Submitting this for review, the pipeline finishes with an Approved verdict and zero reported defects. DiffGuard avoids false positives when changes adhere to secure coding standards."*

### 5. Architectural Reliability & Fallback Demonstration (3:15 – 3:45)
- **Visual:** Open Settings modal. Highlight execution modes.
- **Narration:**
  > *"A cornerstone of DiffGuard's engineering is zero-downtime reliability. If the external Gemini API is unreachable, times out, or experiences quota limits, DiffGuard automatically activates its deterministic fallback engine. Developers always receive an actionable, location-verified review regardless of upstream provider availability.
  >
  > That concludes our live cloud demonstration of DiffGuard."*
