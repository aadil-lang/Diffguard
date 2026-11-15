# DiffGuard — Demonstration Video Recording & Browser Verification Report

**Project:** DiffGuard — AI-Powered Git Diff & Pull Request Review Agent  
**Context:** FLEXGCC AI Engineer Practical Assignment  
**Repository:** `C:\Users\HP\OneDrive\Documents\Diffguard`  
**Date:** 2026-11-15  
**Final Verdict:** `PASS — BROWSER TESTS AND DEMO VIDEO VERIFIED`  

---

## 1. Video Specifications & Artifact Details

| Property | Value / Verification |
| :--- | :--- |
| **Video File Path** | `docs/submission/video/DiffGuard_Demo.mp4` |
| **Container & Codecs** | MP4 (`H.264 / AVC` video + `AAC` stereo audio, web-optimized `+faststart`) |
| **Duration** | **200.26 seconds (3 minutes 20.26 seconds)** — strictly satisfies the 3–5 minute requirement |
| **Resolution** | **1920 × 1080** (Full HD, 16:9 widescreen) |
| **Frame Rate** | 30.0 fps constant |
| **Audio Specifications**| AAC 192 kbps, 44.1 kHz, stereo |
| **Total Bitrate** | 812 kbps |
| **File Size** | **20,334,818 bytes (19.39 MB)** |
| **Recording Engine** | Playwright Chromium (v130+) in headless high-DPI emulation |
| **Narration Engine** | Windows OneCore Neural Speech Synthesis (Microsoft David, natural English) |
| **Muxing & Encoding** | FFmpeg 9.0.2 (libx264 CRF 22 + AAC 192k) |
| **Raw Capture Artifact** | `scratch/raw_videos/page@48ac610ae5fe155de44383c43a2a2303.webm` |

---

## 2. Demonstrated Walkthrough Sequence & Narration Synchronization

The video presents an authentic, continuous walkthrough accompanied by synchronized conversational English voice narration:

```
+-----------------------------------------------------------------------------------------------------------------------+
| Timeline   | Scene & Synchronized Voice Narration                                                                     |
+-----------------------------------------------------------------------------------------------------------------------+
| 0:00–0:34  | Scene 1: Introduction and Settings (Audio: 0.5s – 34.0s)                                                 |
|            | "Hi, this is DiffGuard, an AI-powered code review agent designed to analyze Git diffs and identify       |
|            | potential issues before code changes are merged. The goal is to go beyond simply displaying code         |
|            | warnings. DiffGuard combines deterministic static analysis, an agent-oriented investigation workflow,     |
|            | and structured findings to make code reviews more useful and explainable. Here, I'm opening the settings |
|            | to show the execution configuration and the application's approach to handling API credentials           |
|            | in memory."                                                                                              |
+-----------------------------------------------------------------------------------------------------------------------+
| 0:35–0:56  | Scene 2: Selecting the Vulnerable Sample (Audio: 35.0s – 56.4s)                                          |
|            | "For this demonstration, I'll start with a sample authentication service containing deliberately         |
|            | introduced security issues. The diff includes a hardcoded credential and an S-Q-L query constructed      |
|            | using string formatting. These are the kinds of changes that can introduce serious security              |
|            | vulnerabilities if they make their way into an application."                                             |
+-----------------------------------------------------------------------------------------------------------------------+
| 0:58–1:23  | Scene 3: Running the Review & Progress Stages (Audio: 58.0s – 83.2s)                                      |
|            | "I'll now start the review. DiffGuard processes the submitted changes through a sequence of stages,       |
|            | beginning with input validation and diff decomposition, followed by static analysis and agent            |
|            | reasoning. The final stage validates and formats the findings into a structured review. The progress     |
|            | indicators let us follow the actual review lifecycle rather than treating the model as a black box."     |
+-----------------------------------------------------------------------------------------------------------------------+
| 1:24–2:33  | Scene 4: Reviewing the Findings & Location Navigation (Audio: 84.0s – 152.5s)                             |
|            | "The review has completed with a Critical Blocker verdict. Three findings have been identified.          |
|            | The first is an S-Q-L injection risk in the authentication service... Parameterized queries are the      |
|            | appropriate remediation. The second finding identifies a hardcoded J-W-T secret. Notice that the         |
|            | credential value is redacted in the displayed evidence... The third finding identifies missing test      |
|            | coverage around the authentication logic. I can also select individual findings to navigate directly to  |
|            | their corresponding locations in the diff viewer... Execution note: This demonstration is running         |
|            | through DiffGuard's deterministic fallback engine because a Jem-in-eye API key is not configured..."    |
+-----------------------------------------------------------------------------------------------------------------------+
| 2:33–2:58  | Scene 5: Clean Sample (Audio: 153.5s – 177.4s)                                                           |
|            | "Next, I'll switch to a clean pull-request sample. This example contains a rate-limiter implementation   |
|            | alongside its unit tests. I'll submit it for review using the same workflow. The purpose of this        |
|            | scenario is to demonstrate that a review agent should not just identify potential problems. It should     |
|            | also avoid raising unnecessary findings when the submitted changes appear clean."                        |
+-----------------------------------------------------------------------------------------------------------------------+
| 2:59–3:20  | Scene 6: Final Result and Conclusion (Audio: 179.5s – 200.3s)                                            |
|            | "The review completes with an Approved verdict and zero reported defects. That concludes this DiffGuard  |
|            | demonstration. The project focuses on combining automated code analysis, controlled investigation,      |
|            | structured validation, and traceable findings into a practical code-review workflow. Thank you for       |
|            | watching."                                                                                               |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Playback Verification Evidence

Visual inspection via FFprobe metadata and frame snapshots confirms complete synchrony, clarity, and typography legibility:

1. **`scratch/frame_010s.png` (10s):** Landing view with Navbar, brand title, and Settings Modal.
2. **`scratch/frame_040s.png` (40s):** Diff editor displaying raw `services/auth_service.py` patch.
3. **`scratch/frame_090s.png` (90s):** Summary cards displaying `Verdict: Critical Blocker` and `Engine: deterministic-fallback-engine`.
4. **`scratch/frame_130s.png` (130s):** Finding details card and Diff Viewer highlighting verified line 24 with red defect styling.
5. **`scratch/frame_195s.png` (195s):** Scenario E clean review completion displaying `Verdict: Approved`.

---

## 4. Execution Mode & Security Verification

- **Execution Mode:** The demonstration and voiceover explicitly highlight the **Deterministic Fallback Engine** (`engine_used: "deterministic-fallback-engine"`). No mock or live Gemini API call was fabricated.
- **Sensitive Data & Secrets:**
  - In Scenario A, `JWT_SECRET_KEY = "prod_jwt_super_secret_key_diffguard_9876543210"` is visibly redacted to `JWT_SECRET_KEY = "[REDACTED]"` in the finding card matched code.
  - Zero live user API keys, passwords, or personal credentials are included or exposed in the video.
- **Voice Narration:**
  - Professional, natural English speech generated via native Windows OneCore Neural Speech Synthesis (Microsoft David).
  - Explicit pronunciation compliance: "S-Q-L" (spelled out), "J-W-T" (individual letters), "Jem-in-eye" (Gemini).
  - Clean conversational delivery (~125 words per minute) with natural pauses between scenes.

---

## 5. Final Verification Status

| Item | Status |
| :--- | :--- |
| **Playwright/Chromium Browser Smoke Test** | **VERIFIED** |
| **Scenario A Execution & Verification** | **VERIFIED** (3 findings: SQLi line 24, Secret line 15, Missing tests) |
| **Scenario E Execution & Verification** | **VERIFIED** (Clean Approved verdict, 0 defects) |
| **Finding Location Navigation** | **VERIFIED** (Diff viewer scrolls and highlights lines 24 and 15) |
| **Progress Pipeline & Stage Display** | **VERIFIED** |
| **Synchronized Voice Narration** | **VERIFIED** (Complete natural English audio track with pronunciation compliance) |
| **Video Recording Created** | **VERIFIED** (`docs/submission/video/DiffGuard_Demo.mp4`) |
| **Video Playback & Quality Verified** | **VERIFIED** (1920×1080, 200.26s, 19.39 MB, H.264 + AAC) |
| **Application Source Code Freeze** | **VERIFIED** (Source code untouched, tests passing) |

**Final Verdict:** `PASS — BROWSER TESTS AND DEMO VIDEO VERIFIED`
