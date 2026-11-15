"""
DiffGuard Reviewer Agent: Orchestrates the multi-stage code review workflow.
Integrates unidiff parsing, tool calling, Gemini structured outputs, location validation, and fallback execution.
"""

import json
import logging
import re
import threading
import time
from typing import Callable, Optional, List, Dict, Any

from google import genai
from google.genai import types

from app.config import settings
from app.models.schemas import (
    ReviewRequest,
    ReviewResponse,
    ReviewSummary,
    Finding,
    FindingCategory,
    SeverityLevel,
    FindingConfidence,
    FindingType,
    PolicyEvaluationStatus,
    CodeLocation,
    LocationStatus,
    LineSide,
    SuggestedFix,
    ProcessingStage,
    StageStatus
)
from app.models.diff_models import ParsedDiff
from app.parser.diff_parser import parse_git_diff
from app.parser.location_validator import validate_all_findings, normalize_repo_path
from app.tools.tool_registry import execute_all_analysis_tools
from app.tools.tool_declarations import get_gemini_tools
from app.tools.tool_dispatcher import ToolDispatcher, DEFAULT_MAX_TOOL_CALLS
from app.agent.prompts import DIFFGUARD_SYSTEM_INSTRUCTION, construct_agent_prompt
from app.agent.fallback_engine import run_heuristic_code_review
from app.standards.config_schema import parse_standards_config
from app.standards.rule_engine import EngineeringStandardsEngine
from app.tools.security_scanner import sanitize_diff_content, redact_sensitive_line

logger = logging.getLogger("diffguard.agent")

MAX_INVESTIGATION_TURNS = 3


class CancellationToken:
    """Thread-safe cooperative cancellation token for review execution."""
    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class ReviewCancelledException(Exception):
    """Raised when review is cancelled by client."""
    pass


def sanitize_provider_error(exc: Exception) -> str:
    """
    Transforms raw provider exceptions into safe, human-readable status messages
    without leaking API keys, credentials, or internal endpoints to client or logs.
    """
    err_str = str(exc).lower()
    
    if any(k in err_str for k in ("401", "403", "unauthenticated", "invalid api key", "api_key", "credential", "permission")):
        return "Gemini authentication failed. Please verify your API key."
    if any(k in err_str for k in ("deadline", "timeout", "timed out")):
        return "Gemini request timed out. Please check your network connection."
    if any(k in err_str for k in ("429", "quota", "rate limit", "resource exhausted")):
        return "Gemini quota or rate limit reached. Reverting to fallback review engine."
    if any(k in err_str for k in ("500", "502", "503", "504", "unavailable", "server error")):
        return "Gemini provider service temporarily unavailable. Reverting to fallback review engine."
    if any(k in err_str for k in ("json", "decode", "schema", "validation")):
        return "Invalid or malformed model response. Reverting to fallback review engine."
    
    return "AI provider request failed. Reverting to fallback review engine."


def get_clean_developer_api_schema(pydantic_cls) -> dict:
    """
    Constructs a clean JSON schema dictionary from a Pydantic model for Google GenAI Developer API.
    Strips `additionalProperties` which Developer API mode rejects (supported only in Enterprise mode).
    """
    schema = pydantic_cls.model_json_schema()

    def _strip(d):
        if isinstance(d, dict):
            d.pop("additionalProperties", None)
            for v in d.values():
                _strip(v)
        elif isinstance(d, list):
            for item in d:
                _strip(item)

    _strip(schema)
    return schema


def are_line_sides_compatible(
    side1: Optional[LineSide],
    side2: Optional[LineSide]
) -> bool:
    """
    Determines whether two line sides refer to the same diff location.

    Enforces conservative matching:
    - Explicit OLD and NEW are never compatible (they represent different versions of code).
    - File-level findings only match file-level findings.
    - Missing side information (None) cannot establish safe identity and is treated as
      incompatible to prevent unsafe suppression.
    - BOTH matches BOTH (context lines).
    - Explicit identical sides (NEW == NEW, OLD == OLD, FILE_LEVEL == FILE_LEVEL) are compatible.
    """
    if side1 is None or side2 is None:
        return False

    try:
        s1 = LineSide(side1) if isinstance(side1, str) else side1
        s2 = LineSide(side2) if isinstance(side2, str) else side2
    except ValueError:
        return False

    # Explicit OLD vs NEW is strictly incompatible
    if (s1 == LineSide.OLD and s2 == LineSide.NEW) or (s1 == LineSide.NEW and s2 == LineSide.OLD):
        return False

    # File-level only matches file-level
    if (s1 == LineSide.FILE_LEVEL) != (s2 == LineSide.FILE_LEVEL):
        return False

    # Exact side identity match
    return s1 == s2


def merge_policy_and_model_findings(
    model_findings: List[Finding],
    policy_findings: List[Finding]
) -> List[Finding]:
    """
    Safely merges model-synthesized findings with deterministic engineering standards policy findings.
    
    Invariants enforced:
    1. A genuine code defect is NEVER discarded merely because it shares a file, line, or category with a policy finding.
    2. File paths are canonically normalized (via normalize_repo_path) before location comparison to prevent
       spurious duplicates caused by Git prefix variations (e.g. 'b/path' vs 'path').
    3. Findings referring to different diff sides (OLD vs NEW) are NEVER deduplicated.
    4. Model findings are ONLY treated as duplicates of deterministic policy findings when there is unambiguous,
       explicit policy attribution:
       - Priority 1: Exact matching rule_id (model rule_id == policy rule_id, case-insensitive).
       - Priority 2: In the absence of rule_id, the model finding's title or description contains the exact,
         unambiguous rule ID or exact rule name as a whole word/phrase.
       - Generic category terms (e.g. 'security', 'quality', 'vulnerability', 'risk') are NEVER used to infer attribution.
    5. Deterministic policy findings remain authoritative for their rule metadata, severity, evidence, and remediation.
    6. All un-attributed model findings and all unmatched policy findings are preserved.
    """
    if not policy_findings:
        return list(model_findings)

    merged_findings: List[Finding] = []
    matched_policy_ids = set()

    for f in model_findings:
        colliding_pf = None
        f_norm_path = normalize_repo_path(f.location.file_path) if f.location else ""
        f_line = f.location.start_line if f.location else None
        f_side = f.location.line_side if f.location else None

        for pf in policy_findings:
            if pf.id in matched_policy_ids:
                continue

            pf_norm_path = normalize_repo_path(pf.location.file_path) if pf.location else ""
            pf_line = pf.location.start_line if pf.location else None
            pf_side = pf.location.line_side if pf.location else None

            # 1. Canonical path and line location compatibility
            if not f_norm_path or f_norm_path != pf_norm_path or f_line != pf_line:
                continue

            # 2. Diff-side compatibility: OLD and NEW diff lines must never be collapsed
            if not are_line_sides_compatible(f_side, pf_side):
                continue

            # 3. Priority 1: Explicit matching rule_id
            if f.rule_id and pf.rule_id:
                if f.rule_id.strip().upper() == pf.rule_id.strip().upper():
                    colliding_pf = pf
                    break

            # 4. Priority 2: Explicit policy attribution without rule_id
            # ONLY when structured title or why_identified explicitly contains exact rule_id or exact rule_name.
            # Never infer attribution from broad category words ('security', 'quality', 'vulnerability', 'risk').
            if not f.rule_id:
                f_text = f"{f.title} {f.why_identified}"

                has_exact_rule_id = False
                if pf.rule_id and len(pf.rule_id.strip()) >= 3:
                    rule_id_clean = pf.rule_id.strip()
                    pattern = rf"\b{re.escape(rule_id_clean)}\b"
                    if re.search(pattern, f_text, re.IGNORECASE):
                        has_exact_rule_id = True

                has_exact_rule_name = False
                if pf.rule_name and len(pf.rule_name.strip()) >= 4:
                    rule_name_clean = pf.rule_name.strip()
                    pattern = rf"\b{re.escape(rule_name_clean)}\b"
                    if re.search(pattern, f_text, re.IGNORECASE):
                        has_exact_rule_name = True

                if has_exact_rule_id or has_exact_rule_name:
                    colliding_pf = pf
                    break

        if colliding_pf:
            # Explicit policy duplicate: replace with authoritative deterministic policy finding
            matched_policy_ids.add(colliding_pf.id)
            merged_findings.append(colliding_pf)
        else:
            # Code defect, distinct issue, or un-attributed finding: preserve finding
            merged_findings.append(f)

    # Append any deterministic policy findings not explicitly matched by model
    for pf in policy_findings:
        if pf.id not in matched_policy_ids:
            merged_findings.append(pf)

    return merged_findings


class ReviewAgent:
    """
    Core AI Code Review Agent managing stage progression, tool integration,
    deterministic location validation, and model inference.
    """

    merge_policy_and_model_findings = staticmethod(merge_policy_and_model_findings)
    are_line_sides_compatible = staticmethod(are_line_sides_compatible)

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        # Request-scoped key with fallback to environment configuration
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self._client: Optional[genai.Client] = None
        if self.api_key:
            try:
                http_options = types.HttpOptions(timeout=settings.GEMINI_REQUEST_TIMEOUT_MS)
                self._client = genai.Client(api_key=self.api_key, http_options=http_options)
            except Exception as e:
                sanitized = sanitize_provider_error(e)
                logger.warning(f"Failed to initialise Gemini Client ({type(e).__name__}): {sanitized}")

    def execute_review(
        self,
        request: ReviewRequest,
        on_stage_update: Optional[Callable[[ProcessingStage], None]] = None,
        cancellation_token: Optional[CancellationToken] = None
    ) -> ReviewResponse:
        """
        Execute full end-to-end review with stage tracking, monotonic timeout governance,
        cooperative cancellation, and structured output.
        """
        stages: List[ProcessingStage] = []

        def check_cancellation():
            if cancellation_token and cancellation_token.is_cancelled:
                raise ReviewCancelledException("Review cancelled by client.")

        def update_stage(stage_id: str, name: str, status: StageStatus, details: str = "", duration_ms: Optional[int] = None):
            stage = ProcessingStage(
                stage_id=stage_id,
                name=name,
                status=status,
                details=details,
                duration_ms=duration_ms
            )
            stages.append(stage)
            if on_stage_update and not (cancellation_token and cancellation_token.is_cancelled):
                try:
                    on_stage_update(stage)
                except Exception as e:
                    logger.debug(f"Error in stage callback: {e}")
            return stage

        # Monotonic deadline calculated once per review
        investigation_deadline = time.monotonic() + settings.INVESTIGATION_DEADLINE_SECONDS

        check_cancellation()

        # STAGE 1: Reception & Input Validation
        t0 = time.time()
        update_stage("STAGE_RECEIVED", "Input Validation & Ingestion", StageStatus.IN_PROGRESS, "Validating diff payload and boundary limits...")
        
        if not request.diff_content or not request.diff_content.strip():
            d_ms = int((time.time() - t0) * 1000)
            update_stage("STAGE_RECEIVED", "Input Validation & Ingestion", StageStatus.FAILED, "Empty diff supplied.", d_ms)
            raise ValueError("Diff content cannot be empty.")

        # Validate .diffguard.yaml engineering standards configuration if provided
        try:
            standards_config = parse_standards_config(request.standards_yaml)
        except ValueError as val_err:
            d_ms = int((time.time() - t0) * 1000)
            update_stage("STAGE_RECEIVED", "Input Validation & Ingestion", StageStatus.FAILED, str(val_err), d_ms)
            raise

        d_ms = int((time.time() - t0) * 1000)
        update_stage("STAGE_RECEIVED", "Input Validation & Ingestion", StageStatus.COMPLETED, f"Received {len(request.diff_content):,} bytes of diff text.", d_ms)

        check_cancellation()

        # STAGE 2: Diff Parsing & Structural Decomposition
        t0 = time.time()
        update_stage("STAGE_PARSING", "Unified Diff Decomposition", StageStatus.IN_PROGRESS, "Parsing unified hunks and mapping line ranges with unidiff...")
        
        parsed_diff: ParsedDiff = parse_git_diff(request.diff_content)
        if not parsed_diff.is_valid:
            d_ms = int((time.time() - t0) * 1000)
            update_stage("STAGE_PARSING", "Unified Diff Decomposition", StageStatus.FAILED, parsed_diff.error_message or "Diff parsing failed.", d_ms)
            raise ValueError(parsed_diff.error_message or "Invalid Git diff format.")

        d_ms = int((time.time() - t0) * 1000)
        update_stage(
            "STAGE_PARSING",
            "Unified Diff Decomposition",
            StageStatus.COMPLETED,
            f"Successfully parsed {parsed_diff.total_files} file(s), +{parsed_diff.total_additions} additions, -{parsed_diff.total_deletions} deletions.",
            d_ms
        )

        check_cancellation()

        # STAGE 3: Tool Execution (Security, AST Syntax, Complexity, Test Requirements & Standards)
        t0 = time.time()
        update_stage("STAGE_TOOL_EXECUTION", "Static Tool Analysis & Heuristics", StageStatus.IN_PROGRESS, "Executing security scanner, AST syntax analyzer, complexity metrics, and engineering standards...")

        tool_results = execute_all_analysis_tools(parsed_diff)
        sec_count = len(tool_results.get("security_findings", []))
        syn_count = len(tool_results.get("syntax_findings", []))
        comp_count = len(tool_results.get("complexity_findings", []))
        test_count = len(tool_results.get("test_coverage_findings", []))

        # Evaluate Deterministic Engineering Standards (.diffguard.yaml)
        standards_engine = EngineeringStandardsEngine(standards_config)
        policy_findings = standards_engine.evaluate(parsed_diff)
        policy_status = standards_engine.get_rules_status()
        policy_violations_count = len(policy_findings)

        d_ms = int((time.time() - t0) * 1000)
        update_stage(
            "STAGE_TOOL_EXECUTION",
            "Static Tool Analysis & Heuristics",
            StageStatus.COMPLETED,
            f"Tools completed: {sec_count} security detection(s), {syn_count} syntax issue(s), {comp_count} complexity alert(s), {test_count} test gap(s). Standards: {policy_status['active_rules_count']} active rule(s) evaluated ({policy_violations_count} violation(s)).",
            d_ms
        )

        check_cancellation()

        # STAGE 4: Agent Reasoning & LLM Inference
        t0 = time.time()
        update_stage("STAGE_AGENT_REASONING", "AI Agent Synthesis & Reasoning", StageStatus.IN_PROGRESS, "Agent analyzing diff semantics, edge cases, and tool findings...")

        # Format summary & tool evidence for prompt
        files_summary = "\n".join([
            f"- {f.target_file} ({f.language}): +{f.additions}/-{f.deletions} lines across {len(f.hunks)} hunk(s)"
            for f in parsed_diff.files
        ])
        tool_evidence_str = json.dumps(tool_results, indent=2)
        standards_summary_str = json.dumps(policy_status, indent=2)

        # Enforce external LLM data boundary (B1 / F-SEC-02):
        # Sanitize raw diff to ensure unredacted credentials never enter prompt or external model calls
        disclosure_safe_diff = sanitize_diff_content(request.diff_content)

        prompt = construct_agent_prompt(
            parsed_diff_summary=files_summary,
            raw_diff=disclosure_safe_diff,
            tool_evidence=tool_evidence_str,
            custom_instructions=request.custom_instructions or "",
            standards_summary=standards_summary_str
        )

        ai_review_response: Optional[ReviewResponse] = None

        # Check if custom API key was passed in request (strictly request-scoped)
        active_client = self._client
        if request.api_key:
            try:
                http_options = types.HttpOptions(timeout=settings.GEMINI_REQUEST_TIMEOUT_MS)
                active_client = genai.Client(api_key=request.api_key, http_options=http_options)
            except Exception as e:
                sanitized_err = sanitize_provider_error(e)
                logger.warning(f"Custom API key could not initialize client: {sanitized_err}")

        if active_client:
            try:
                model_to_use = request.model_name or self.model_name
                logger.info(f"Invoking Gemini model with two-phase governed investigation: {model_to_use}")

                # Initialize request-scoped tool dispatcher with disclosure-safe parsed diff
                sanitized_parsed_diff = parse_git_diff(disclosure_safe_diff)
                dispatcher = ToolDispatcher(parsed_diff=sanitized_parsed_diff, max_tool_calls=DEFAULT_MAX_TOOL_CALLS)
                tools = get_gemini_tools()

                # Phase A: Governed Investigation Loop (ReAct)
                conversation_history: List[types.Content] = [
                    types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
                ]

                investigation_turn = 0

                update_stage(
                    "STAGE_AGENT_REASONING",
                    "AI Agent Synthesis & Reasoning",
                    StageStatus.IN_PROGRESS,
                    "Agent initiating model-directed investigation with diff inspection tools..."
                )

                while investigation_turn < MAX_INVESTIGATION_TURNS:
                    check_cancellation()

                    remaining_sec = investigation_deadline - time.monotonic()
                    if remaining_sec <= 0:
                        logger.warning("Investigation monotonic deadline reached (60s); advancing to final synthesis.")
                        update_stage(
                            "STAGE_AGENT_REASONING",
                            "AI Agent Synthesis & Reasoning",
                            StageStatus.IN_PROGRESS,
                            "Investigation deadline reached; advancing to final findings synthesis."
                        )
                        break

                    req_timeout_ms = min(int(remaining_sec * 1000), settings.GEMINI_REQUEST_TIMEOUT_MS)
                    if req_timeout_ms < 1000:
                        logger.warning("Insufficient time remaining for upstream call (<1s); advancing.")
                        break

                    investigation_config = types.GenerateContentConfig(
                        system_instruction=DIFFGUARD_SYSTEM_INSTRUCTION,
                        temperature=0.2,
                        tools=tools,
                        http_options=types.HttpOptions(timeout=req_timeout_ms)
                    )

                    resp = active_client.models.generate_content(
                        model=model_to_use,
                        contents=list(conversation_history),
                        config=investigation_config
                    )

                    check_cancellation()

                    if not resp.candidates or not resp.candidates[0].content:
                        logger.warning("Gemini returned empty candidate content during investigation.")
                        break

                    # Preserve the complete model response content (function calls, thoughts, text)
                    model_content = resp.candidates[0].content
                    conversation_history.append(model_content)

                    function_calls = resp.function_calls or []
                    if not function_calls:
                        # Model concluded investigation without requesting additional tools
                        update_stage(
                            "STAGE_AGENT_REASONING",
                            "AI Agent Synthesis & Reasoning",
                            StageStatus.IN_PROGRESS,
                            f"Investigation concluded in turn {investigation_turn + 1}. All empirical evidence evaluated."
                        )
                        break

                    update_stage(
                        "STAGE_AGENT_REASONING",
                        "AI Agent Synthesis & Reasoning",
                        StageStatus.IN_PROGRESS,
                        f"Turn {investigation_turn + 1}: Model requested {len(function_calls)} inspection tool call(s)..."
                    )

                    tool_response_parts: List[types.Part] = []
                    for fc in function_calls:
                        check_cancellation()
                        update_stage(
                            "STAGE_AGENT_REASONING",
                            "AI Agent Synthesis & Reasoning",
                            StageStatus.IN_PROGRESS,
                            f"Executing tool '{fc.name}'..."
                        )
                        tool_res = dispatcher.dispatch(fc.name, fc.args)
                        status_label = "cached" if tool_res.cached else ("success" if tool_res.success else f"error ({tool_res.error_code})")
                        update_stage(
                            "STAGE_AGENT_REASONING",
                            "AI Agent Synthesis & Reasoning",
                            StageStatus.IN_PROGRESS,
                            f"Tool '{fc.name}' completed [{status_label}]."
                        )
                        part = dispatcher.to_function_response_part(fc.name, tool_res)
                        tool_response_parts.append(part)

                    tool_content = types.Content(role="user", parts=tool_response_parts)
                    conversation_history.append(tool_content)
                    investigation_turn += 1

                # Phase B: Final Structured Synthesis
                check_cancellation()

                remaining_sec = investigation_deadline - time.monotonic()
                if remaining_sec <= 1.0:
                    logger.warning("Investigation deadline expired before synthesis; triggering fallback review engine.")
                    update_stage(
                        "STAGE_AGENT_REASONING",
                        "AI Agent Synthesis & Reasoning",
                        StageStatus.IN_PROGRESS,
                        "Investigation deadline expired before synthesis; triggering fallback review engine."
                    )
                else:
                    update_stage(
                        "STAGE_AGENT_REASONING",
                        "AI Agent Synthesis & Reasoning",
                        StageStatus.IN_PROGRESS,
                        f"Synthesizing final review report ({dispatcher.calls_count} tool call(s) executed)..."
                    )

                    synthesis_instruction = types.Content(
                        role="user",
                        parts=[types.Part.from_text(
                            text="Investigation complete. Synthesize your final code review findings, root causes, impacts, suggested fixes, and overall verdict now according to the structured ReviewResponse JSON schema."
                        )]
                    )

                    synth_timeout_ms = min(int(remaining_sec * 1000), settings.GEMINI_REQUEST_TIMEOUT_MS)
                    synthesis_config = types.GenerateContentConfig(
                        system_instruction=DIFFGUARD_SYSTEM_INSTRUCTION,
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=get_clean_developer_api_schema(ReviewResponse),
                        tools=None,  # Explicitly disable tools for structured synthesis
                        http_options=types.HttpOptions(timeout=synth_timeout_ms)
                    )

                    final_response = active_client.models.generate_content(
                        model=model_to_use,
                        contents=conversation_history + [synthesis_instruction],
                        config=synthesis_config
                    )

                    check_cancellation()

                    if final_response.text:
                        parsed_json = json.loads(final_response.text)
                        ai_review_response = ReviewResponse.model_validate(parsed_json)
                        tool_summary_suffix = f" [{dispatcher.calls_count} tool call(s)]" if dispatcher.calls_count > 0 else ""
                        ai_review_response.engine_used = f"gemini-agent ({model_to_use}){tool_summary_suffix}"

            except ReviewCancelledException:
                raise
            except Exception as e:
                sanitized_msg = sanitize_provider_error(e)
                logger.warning(f"Gemini API inference note ({type(e).__name__}): {sanitized_msg}")
                update_stage(
                    "STAGE_AGENT_REASONING",
                    "AI Agent Synthesis & Reasoning",
                    StageStatus.COMPLETED,
                    f"{sanitized_msg} Fallback engine activated to guarantee reliability."
                )

        check_cancellation()

        if ai_review_response:
            # Deterministic policy merge: ensure Gemini cannot omit configured repository standards,
            # distort finding types, or duplicate findings when emitting policy observations with explicit attribution.
            # Enforces canonical path matching and preserves all genuine code defects.
            ai_review_response.findings = merge_policy_and_model_findings(
                ai_review_response.findings,
                policy_findings
            )
        else:
            # Execute deterministic heuristic review with policy findings
            ai_review_response = run_heuristic_code_review(
                parsed_diff, tool_results, stages, policy_findings=policy_findings
            )

        d_ms = int((time.time() - t0) * 1000)
        update_stage(
            "STAGE_AGENT_REASONING",
            "AI Agent Synthesis & Reasoning",
            StageStatus.COMPLETED,
            f"Review synthesized using {ai_review_response.engine_used}.",
            d_ms
        )

        check_cancellation()

        # STAGE 5: Structured Schema Validation & Location Integrity Verification
        t0 = time.time()
        update_stage("STAGE_STRUCTURED_VALIDATION", "Findings Validation & Formatting", StageStatus.IN_PROGRESS, "Validating locations against diff hunks, checking bounds, and formatting remediation...")

        # Deterministic location validation: cross-references findings against actual diff hunks
        ai_review_response.findings = validate_all_findings(ai_review_response.findings, parsed_diff)

        # Centralized disclosure-safe sanitization of all output finding fields
        for f in ai_review_response.findings:
            if f.location and f.location.code_context:
                f.location.code_context = redact_sensitive_line(f.location.code_context)
            if f.why_identified:
                f.why_identified = redact_sensitive_line(f.why_identified)
            if f.suggested_fix and f.suggested_fix.replacement_code:
                f.suggested_fix.replacement_code = redact_sensitive_line(f.suggested_fix.replacement_code)

        # Recalculate summary metrics distinguishing defects from policy violations
        by_type: Dict[str, int] = {t.value: 0 for t in FindingType}
        total_defects = 0
        total_policy_violations = 0
        total_recommendations = 0

        for f in ai_review_response.findings:
            ftype = f.finding_type or FindingType.CODE_DEFECT
            by_type[ftype.value] = by_type.get(ftype.value, 0) + 1
            if ftype == FindingType.POLICY_VIOLATION:
                total_policy_violations += 1
            elif ftype == FindingType.RECOMMENDATION:
                total_recommendations += 1
            else:
                total_defects += 1

        ai_review_response.summary.total_defects = total_defects
        ai_review_response.summary.total_policy_violations = total_policy_violations
        ai_review_response.summary.total_recommendations = total_recommendations
        ai_review_response.summary.by_finding_type = by_type
        ai_review_response.summary.total_findings = len(ai_review_response.findings)

        # Ensure correct file counts and stages
        ai_review_response.parsed_files_count = parsed_diff.total_files
        ai_review_response.total_additions = parsed_diff.total_additions
        ai_review_response.total_deletions = parsed_diff.total_deletions
        ai_review_response.stages_executed = stages

        verified_count = sum(
            1 for f in ai_review_response.findings
            if f.location.location_status in (LocationStatus.VERIFIED, LocationStatus.FILE_LEVEL)
        )

        d_ms = int((time.time() - t0) * 1000)
        update_stage(
            "STAGE_STRUCTURED_VALIDATION",
            "Findings Validation & Formatting",
            StageStatus.COMPLETED,
            f"Validated {len(ai_review_response.findings)} finding(s) ({verified_count} verified against patch). Verdict: {ai_review_response.summary.verdict}.",
            d_ms
        )

        return ai_review_response
