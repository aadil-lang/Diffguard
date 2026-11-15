# DiffGuard — Demonstration Video Narration Transcript

**Video Target:** `docs/submission/video/DiffGuard_Demo.mp4`  
**Duration:** 3 minutes 20.26 seconds (200.26 s)  
**Resolution:** 1920 × 1080 (Full HD, 16:9 widescreen)  
**Style:** Professional engineering explanation, natural neutral English voiceover  
**Audio Track:** AAC-LC Stereo, 192 kbps, 44.1 kHz  

---

## Complete Verbatim Narration Transcript

### Scene 1: Introduction and Settings (0:00 – 0:30)

**[Visual Cue: 0:00–0:12]** DiffGuard dashboard opens at `http://localhost:3000`. Visual overview of the layout: header, unified diff editor, sample scenario dropdown, and review execution panel.  
**[Visual Cue: 0:12–0:30]** Clicks the "Settings" button. Settings modal opens showcasing the execution configuration, model selection, and ephemeral API credential management notice.

> *"Hi, this is DiffGuard, an AI-powered code review agent designed to analyze Git diffs and identify potential issues before code changes are merged.*
>
> *The goal is to go beyond simply displaying code warnings. DiffGuard combines deterministic static analysis, an agent-oriented investigation workflow, and structured findings to make code reviews more useful and explainable.*
>
> *Here, I'm opening the settings to show the execution configuration and the application's approach to handling API credentials in memory."*

---

### Scene 2: Selecting the Vulnerable Sample (0:30 – 0:55)

**[Visual Cue: 0:30–0:42]** Closes Settings. Selects `sample-sqli-auth` from the sample dropdown.  
**[Visual Cue: 0:42–0:55]** Scrolls through the diff editor highlighting the added lines in `services/auth_service.py`: a hardcoded JWT secret on line 15 and raw SQL query string formatting on line 24.

> *"For this demonstration, I'll start with a sample authentication service containing deliberately introduced security issues.*
>
> *The diff includes a hardcoded credential and an SQL query constructed using string formatting.*
>
> *These are the kinds of changes that can introduce serious security vulnerabilities if they make their way into an application."*

---

### Scene 3: Running the Review (0:55 – 1:30)

**[Visual Cue: 0:55–1:15]** Clicks the "Start AI Code Review" button.  
**[Visual Cue: 1:15–1:30]** Real-time progress indicators display execution across active pipeline stages: *Sanitize Diff $\to$ AST Parsing $\to$ Static Tool Execution $\to$ Agent Reasoning $\to$ Report Synthesis*.

> *"I'll now start the review.*
>
> *DiffGuard processes the submitted changes through a sequence of stages, beginning with input validation and diff decomposition, followed by static analysis and agent reasoning.*
>
> *The final stage validates and formats the findings into a structured review.*
>
> *The progress indicators let us follow the actual review lifecycle rather than treating the model as a black box."*

---

### Scene 4: Reviewing Findings and Diff Navigation (1:30 – 2:25)

**[Visual Cue: 1:30–1:48]** Review completes. The Summary Cards display: Verdict **"Needs Attention"** (Critical Blocker) and engine badge `Engine: deterministic-fallback-engine`.  
**[Visual Cue: 1:48–2:04]** Inspects Finding 1 (Critical SQL Injection Risk on line 24). Clicks "Navigate to diff location" — DiffViewer scrolls and highlights line 24.  
**[Visual Cue: 2:04–2:16]** Inspects Finding 2 (Hardcoded JWT secret on line 15 with redacted evidence). Clicks location navigation to line 15.  
**[Visual Cue: 2:16–2:25]** Inspects Finding 3 (Missing unit test coverage for authentication logic).

> *"The review has completed with a Critical Blocker verdict. Three findings have been identified.*
>
> *The first is an SQL injection risk in the authentication service. The issue occurs because user-controlled values are incorporated into an SQL query through string formatting. Parameterized queries are the appropriate remediation.*
>
> *The second finding identifies a hardcoded JWT secret. Notice that the credential value is redacted in the displayed evidence. This is important because a security scanner should not introduce another disclosure risk while reporting an existing one.*
>
> *The third finding identifies missing test coverage around the authentication logic.*
>
> *I can also select individual findings to navigate directly to their corresponding locations in the diff viewer. Here, the application scrolls to the relevant line and highlights the finding. This connects the review output with the actual code change, making it easier to investigate and verify.*
>
> *Execution note: This demonstration is running through DiffGuard's deterministic fallback engine because a Gemini API key is not configured. The Gemini model selection shown in the interface should not be confused with live Gemini execution in this recording."*

---

### Scene 5: Running a Clean Code Sample (2:25 – 3:05)

**[Visual Cue: 2:25–2:45]** Selects `sample-clean-pr` from the dropdown (rate limiter implementation with accompanying unit tests).  
**[Visual Cue: 2:45–3:05]** Clicks "Start AI Code Review". Pipeline completes cleanly.

> *"Next, I'll switch to a clean pull-request sample. This example contains a rate-limiter implementation alongside its unit tests. I'll submit it for review using the same workflow.*
>
> *The purpose of this scenario is to demonstrate that a review agent should not just identify potential problems. It should also avoid raising unnecessary findings when the submitted changes appear clean."*

---

### Scene 6: Final Result and Conclusion (3:05 – 3:20)

**[Visual Cue: 3:05–3:20]** Review summary renders an **Approved** verdict with **0 reported defects**. Mouse smoothly highlights the clean findings summary.

> *"The review completes with an Approved verdict and zero reported defects.*
>
> *That concludes this DiffGuard demonstration. The project focuses on combining automated code analysis, controlled investigation, structured validation, and traceable findings into a practical code-review workflow.*
>
> *Thank you for watching."*
