"""
DiffGuard Reviewer Agent: Orchestrates the multi-stage code review workflow.
Integrates unidiff parsing, tool calling, Gemini structured outputs, and fallback execution.
"""

import json
import logging
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
    CodeLocation,
    SuggestedFix,
    ProcessingStage,
    StageStatus
)
from app.models.diff_models import ParsedDiff
from app.parser.diff_parser import parse_git_diff
from app.tools.tool_registry import execute_all_analysis_tools
from app.agent.prompts import DIFFGUARD_SYSTEM_INSTRUCTION, construct_agent_prompt
from app.agent.fallback_engine import run_heuristic_code_review

logger = logging.getLogger("diffguard.agent")


class ReviewAgent:
    """
    Core AI Code Review Agent managing stage progression, tool integration,
    and model inference.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self._client: Optional[genai.Client] = None
        if self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialise Gemini Client: {e}")

    def execute_review(
        self,
        request: ReviewRequest,
        on_stage_update: Optional[Callable[[ProcessingStage], None]] = None
    ) -> ReviewResponse:
        """
        Execute full end-to-end review with stage tracking and structured output.
        """
        stages: List[ProcessingStage] = []

        def update_stage(stage_id: str, name: str, status: StageStatus, details: str = "", duration_ms: Optional[int] = None):
            stage = ProcessingStage(
                stage_id=stage_id,
                name=name,
                status=status,
                details=details,
                duration_ms=duration_ms
            )
            stages.append(stage)
            if on_stage_update:
                try:
                    on_stage_update(stage)
                except Exception as e:
                    logger.debug(f"Error in stage callback: {e}")
            return stage

        # STAGE 1: Reception & Input Validation
        t0 = time.time()
        update_stage("STAGE_RECEIVED", "Input Validation & Ingestion", StageStatus.IN_PROGRESS, "Validating diff payload and boundary limits...")
        
        if not request.diff_content or not request.diff_content.strip():
            d_ms = int((time.time() - t0) * 1000)
            update_stage("STAGE_RECEIVED", "Input Validation & Ingestion", StageStatus.FAILED, "Empty diff supplied.", d_ms)
            raise ValueError("Diff content cannot be empty.")

        d_ms = int((time.time() - t0) * 1000)
        update_stage("STAGE_RECEIVED", "Input Validation & Ingestion", StageStatus.COMPLETED, f"Received {len(request.diff_content):,} bytes of diff text.", d_ms)

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

        # STAGE 3: Tool Execution (Security, AST Syntax, Complexity, Test Requirements)
        t0 = time.time()
        update_stage("STAGE_TOOL_EXECUTION", "Static Tool Analysis & Heuristics", StageStatus.IN_PROGRESS, "Executing security scanner, AST syntax analyzer, and complexity metrics...")

        tool_results = execute_all_analysis_tools(parsed_diff)
        sec_count = len(tool_results.get("security_findings", []))
        syn_count = len(tool_results.get("syntax_findings", []))
        comp_count = len(tool_results.get("complexity_findings", []))
        test_count = len(tool_results.get("test_coverage_findings", []))

        d_ms = int((time.time() - t0) * 1000)
        update_stage(
            "STAGE_TOOL_EXECUTION",
            "Static Tool Analysis & Heuristics",
            StageStatus.COMPLETED,
            f"Tools completed: {sec_count} security detection(s), {syn_count} syntax issue(s), {comp_count} complexity alert(s), {test_count} test gap(s).",
            d_ms
        )

        # STAGE 4: Agent Reasoning & LLM Inference
        t0 = time.time()
        update_stage("STAGE_AGENT_REASONING", "AI Agent Synthesis & Reasoning", StageStatus.IN_PROGRESS, "Agent analyzing diff semantics, edge cases, and tool findings...")

        # Format summary & tool evidence for prompt
        files_summary = "\n".join([
            f"- {f.target_file} ({f.language}): +{f.additions}/-{f.deletions} lines across {len(f.hunks)} hunk(s)"
            for f in parsed_diff.files
        ])
        tool_evidence_str = json.dumps(tool_results, indent=2)

        prompt = construct_agent_prompt(
            parsed_diff_summary=files_summary,
            raw_diff=request.diff_content,
            tool_evidence=tool_evidence_str,
            custom_instructions=request.custom_instructions or ""
        )

        ai_review_response: Optional[ReviewResponse] = None

        # Check if custom API key was passed in request
        active_client = self._client
        if request.api_key:
            try:
                active_client = genai.Client(api_key=request.api_key)
            except Exception as e:
                logger.warning(f"Custom API key could not initialize client: {e}")

        if active_client:
            try:
                model_to_use = request.model_name or self.model_name
                logger.info(f"Invoking Gemini model: {model_to_use}")

                config = types.GenerateContentConfig(
                    system_instruction=DIFFGUARD_SYSTEM_INSTRUCTION,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=ReviewResponse
                )

                response = active_client.models.generate_content(
                    model=model_to_use,
                    contents=prompt,
                    config=config
                )

                if response.text:
                    parsed_json = json.loads(response.text)
                    # Validate against Pydantic schema
                    ai_review_response = ReviewResponse.model_validate(parsed_json)
                    ai_review_response.engine_used = f"gemini-agent ({model_to_use})"

            except Exception as e:
                logger.warning(f"Gemini API inference error or malformed response: {e}. Falling back to deterministic engine.")
                update_stage(
                    "STAGE_AGENT_REASONING",
                    "AI Agent Synthesis & Reasoning",
                    StageStatus.COMPLETED,
                    f"Gemini API note: {str(e)[:120]}... Fallback engine activated to guarantee reliability."
                )

        if not ai_review_response:
            # Execute deterministic heuristic review
            ai_review_response = run_heuristic_code_review(parsed_diff, tool_results, stages)

        d_ms = int((time.time() - t0) * 1000)
        update_stage(
            "STAGE_AGENT_REASONING",
            "AI Agent Synthesis & Reasoning",
            StageStatus.COMPLETED,
            f"Review synthesized using {ai_review_response.engine_used}.",
            d_ms
        )

        # STAGE 5: Structured Schema Validation & Enrichment
        t0 = time.time()
        update_stage("STAGE_STRUCTURED_VALIDATION", "Findings Validation & Formatting", StageStatus.IN_PROGRESS, "Validating locations, severity distributions, and actionable remediation...")

        # Ensure correct file counts and stages
        ai_review_response.parsed_files_count = parsed_diff.total_files
        ai_review_response.total_additions = parsed_diff.total_additions
        ai_review_response.total_deletions = parsed_diff.total_deletions
        ai_review_response.stages_executed = stages

        d_ms = int((time.time() - t0) * 1000)
        update_stage(
            "STAGE_STRUCTURED_VALIDATION",
            "Findings Validation & Formatting",
            StageStatus.COMPLETED,
            f"Generated {len(ai_review_response.findings)} structured finding(s). Verdict: {ai_review_response.summary.verdict}.",
            d_ms
        )

        return ai_review_response

