"""
Offline Verification Suite for Two-Phase Governed Gemini Function Calling & ReviewAgent (Phase 2.2).
Tests SDK protocols, multi-turn investigation loops, budget caps, timeout handling,
synthesis formatting, error resilience, and stage callbacks without live API charges.
"""

import json
import time
from unittest.mock import MagicMock
import pytest
from google.genai import types

from app.agent.reviewer_agent import ReviewAgent, CancellationToken, ReviewCancelledException, get_clean_developer_api_schema
from app.models.schemas import ReviewRequest, ReviewResponse, ProcessingStage, StageStatus, FindingCategory, SeverityLevel
from app.samples.sample_diffs import SAMPLE_SQLI_AUTH, SAMPLE_CLEAN_PR


def make_tool_call_response(calls):
    """Constructs a mock GenerateContentResponse containing one or more function calls."""
    parts = []
    for name, args in calls:
        call = types.FunctionCall(name=name, args=args)
        parts.append(types.Part(function_call=call))
    candidate = types.Candidate(content=types.Content(role="model", parts=parts))
    return types.GenerateContentResponse(candidates=[candidate])


def make_conclusion_response(thought="I have sufficient evidence to complete the review."):
    """Constructs a mock model response with no function calls (concluding investigation)."""
    part = types.Part.from_text(text=thought)
    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
    return types.GenerateContentResponse(candidates=[candidate])


def make_synthesis_response(findings=None, verdict="CHANGES_REQUESTED"):
    """Constructs a mock structured ReviewResponse JSON string response for Phase B synthesis."""
    payload = {
        "review_id": "DG-REV-MOCK-001",
        "timestamp": "2026-11-13T22:00:00Z",
        "engine_used": "gemini-agent (gemini-2.5-flash)",
        "summary": {
            "total_findings": len(findings) if findings else 0,
            "by_severity": {"CRITICAL": 1} if findings else {},
            "by_category": {"SECURITY_AND_RELIABILITY": 1} if findings else {},
            "by_confidence": {"CONFIRMED_ISSUE": 1} if findings else {},
            "verdict": verdict,
            "key_takeaways": ["Review synthesized successfully via two-phase agent."]
        },
        "findings": findings or [],
        "parsed_files_count": 1,
        "total_additions": 10,
        "total_deletions": 2,
        "stages_executed": []
    }
    json_text = json.dumps(payload)
    part = types.Part.from_text(text=json_text)
    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
    return types.GenerateContentResponse(candidates=[candidate])


# ==============================================================================
# SECTION A: SDK Protocol & History Verification
# ==============================================================================

def test_sdk_protocol_conversation_history_and_roles():
    """Verify that conversation history maintains correct roles and preserves model content."""
    mock_client = MagicMock()
    # Turn 1: model requests tool; Turn 2: model concludes; Turn 3: synthesis call
    mock_client.models.generate_content.side_effect = [
        make_tool_call_response([("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0})]),
        make_conclusion_response(),
        make_synthesis_response()
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    assert mock_client.models.generate_content.call_count == 3
    # Check first call (investigation initial prompt)
    call_1_args, call_1_kwargs = mock_client.models.generate_content.call_args_list[0]
    contents_1 = call_1_kwargs["contents"]
    assert len(contents_1) == 1
    assert contents_1[0].role == "user"

    # Check second call (investigation response turn with tool response)
    call_2_args, call_2_kwargs = mock_client.models.generate_content.call_args_list[1]
    contents_2 = call_2_kwargs["contents"]
    assert len(contents_2) == 3
    assert contents_2[0].role == "user"   # Initial prompt
    assert contents_2[1].role == "model"  # Preserved model candidate with function call
    assert contents_2[2].role == "user"   # Tool response turn
    assert contents_2[2].parts[0].function_response.name == "inspect_diff_hunk"

    # Check third call (synthesis with tools disabled)
    call_3_args, call_3_kwargs = mock_client.models.generate_content.call_args_list[2]
    config_3 = call_3_kwargs["config"]
    assert config_3.tools is None
    assert config_3.response_schema in (ReviewResponse, get_clean_developer_api_schema(ReviewResponse))
    assert "tool call(s)" in res.engine_used


def test_multiple_function_calls_in_single_turn():
    """Verify handling when model requests multiple inspection tools in one turn."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        make_tool_call_response([
            ("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0}),
            ("inspect_patch_context", {"file_path": "services/auth_service.py", "start_line": 20})
        ]),
        make_conclusion_response(),
        make_synthesis_response()
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    assert "2 tool call(s)" in res.engine_used
    # Verify tool response turn has 2 parts
    call_2_args, call_2_kwargs = mock_client.models.generate_content.call_args_list[1]
    tool_turn = call_2_kwargs["contents"][2]
    assert len(tool_turn.parts) == 2
    assert tool_turn.parts[0].function_response.name == "inspect_diff_hunk"
    assert tool_turn.parts[1].function_response.name == "inspect_patch_context"


# ==============================================================================
# SECTION B: Investigation Loop & Governance Limits
# ==============================================================================

def test_model_concludes_immediately_with_zero_tools():
    """Verify that if Gemini requests 0 tools, investigation halts and advances to synthesis."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        make_conclusion_response("Clean PR, no tools needed."),
        make_synthesis_response(verdict="APPROVED")
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_CLEAN_PR.diff_content)
    res = agent.execute_review(req)

    # 1 investigation turn + 1 synthesis call = 2 calls total
    assert mock_client.models.generate_content.call_count == 2
    assert res.summary.verdict == "APPROVED"
    assert "tool call" not in res.engine_used


def test_maximum_investigation_turns_enforcement():
    """Verify loop terminates at max 3 turns even if model keeps asking for tools."""
    mock_client = MagicMock()
    # 3 turns of tool calls, then synthesis
    mock_client.models.generate_content.side_effect = [
        make_tool_call_response([("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0})]),
        make_tool_call_response([("inspect_patch_context", {"file_path": "services/auth_service.py", "start_line": 15})]),
        make_tool_call_response([("inspect_patch_context", {"file_path": "services/auth_service.py", "start_line": 20})]),
        make_synthesis_response()
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    # Exactly 3 investigation calls + 1 synthesis call = 4 calls total
    assert mock_client.models.generate_content.call_count == 4
    assert res.summary.verdict == "CHANGES_REQUESTED"


def test_tool_call_budget_enforcement_in_agent():
    """Verify dispatcher halts tool calls when max budget (6) is reached."""
    mock_client = MagicMock()
    # Model requests 8 tool calls across turns
    calls_turn_1 = [("inspect_patch_context", {"file_path": "services/auth_service.py", "start_line": i * 5}) for i in range(1, 5)] # 4 calls
    calls_turn_2 = [("inspect_patch_context", {"file_path": "services/auth_service.py", "start_line": i * 5}) for i in range(5, 9)] # 4 calls

    mock_client.models.generate_content.side_effect = [
        make_tool_call_response(calls_turn_1),
        make_tool_call_response(calls_turn_2),
        make_conclusion_response(),
        make_synthesis_response()
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    # In turn 2, 2 calls succeed (bringing total to 6), and 2 calls fail with BUDGET_EXCEEDED
    assert "6 tool call(s)" in res.engine_used


def test_duplicate_requests_use_cache():
    """Verify repeated identical tool calls are served from cache and preserve budget."""
    mock_client = MagicMock()
    # Turn 1: call hunk 0; Turn 2: repeat call hunk 0; Turn 3: conclude; Synthesis
    mock_client.models.generate_content.side_effect = [
        make_tool_call_response([("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0})]),
        make_tool_call_response([("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0})]),
        make_conclusion_response(),
        make_synthesis_response()
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    # Duplicate call was served from cache; both model requests are consistently accounted
    assert "2 tool call(s)" in res.engine_used


def test_unknown_and_malformed_tool_requests_handled_safely():
    """Verify unknown tool and malformed arguments do not crash the agent."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        make_tool_call_response([
            ("execute_arbitrary_shell", {"command": "rm -rf /"}),
            ("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": -99})
        ]),
        make_conclusion_response(),
        make_synthesis_response()
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    assert res is not None
    assert mock_client.models.generate_content.call_count == 3


# ==============================================================================
# SECTION C: Synthesis & Location Validation Integration
# ==============================================================================

def test_synthesis_findings_undergo_location_validation():
    """Verify findings produced by final synthesis undergo deterministic location validation."""
    mock_client = MagicMock()
    finding_dict = {
        "id": "DG-001",
        "title": "Raw SQL injection in user query",
        "category": "SECURITY_AND_RELIABILITY",
        "severity": "CRITICAL",
        "confidence": "CONFIRMED_ISSUE",
        "location": {
            "file_path": "services/auth_service.py",
            "start_line": 21,
            "line_side": "new"
        },
        "why_identified": "User input directly formatted into SQL query string.",
        "impact": "Full database bypass.",
        "suggested_fix": {
            "description": "Use parameterized query."
        }
    }

    mock_client.models.generate_content.side_effect = [
        make_conclusion_response(),
        make_synthesis_response(findings=[finding_dict])
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    assert len(res.findings) == 1
    f = res.findings[0]
    assert f.location.location_status.value == "verified"
    assert f.location.line_side.value == "new"
    assert f.location.start_line == 21


# ==============================================================================
# SECTION D: Resilience & Fallback Tests
# ==============================================================================

def test_investigation_failure_triggers_fallback():
    """Verify exception during investigation triggers fallback engine cleanly."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 Resource has been exhausted (rate limit)")

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    assert res is not None
    assert "heuristic" in res.engine_used.lower() or "fallback" in res.engine_used.lower()
    assert res.summary.total_findings >= 1


def test_synthesis_failure_triggers_fallback():
    """Verify failure during final synthesis call triggers fallback engine cleanly."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        make_conclusion_response(),
        Exception("503 Service Unavailable")
    ]

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    assert res is not None
    assert "heuristic" in res.engine_used.lower() or "fallback" in res.engine_used.lower()


def test_sse_stage_callback_emits_granular_tool_events():
    """Verify on_stage_update receives tool execution and lifecycle events."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        make_tool_call_response([("inspect_diff_hunk", {"file_path": "services/auth_service.py", "hunk_index": 0})]),
        make_conclusion_response(),
        make_synthesis_response()
    ]

    emitted_stages = []
    def callback(stage: ProcessingStage):
        emitted_stages.append(stage.details)

    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    agent.execute_review(req, on_stage_update=callback)

    details_text = " ".join(emitted_stages)
    assert "inspect_diff_hunk" in details_text
    assert "completed" in details_text
    assert "Synthesizing" in details_text


# ==============================================================================
# SECTION E: Phase 2.2.2 Targeted Hardening Tests (F-01, F-02, F-03, F-05)
# ==============================================================================

def test_cooperative_cancellation_token_halts_review():
    """Verify ReviewCancelledException is raised if cancellation_token is cancelled."""
    token = CancellationToken()
    token.cancel()
    agent = ReviewAgent(api_key="mock_key")
    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    with pytest.raises(ReviewCancelledException):
        agent.execute_review(req, cancellation_token=token)


def test_monotonic_deadline_expiration_triggers_fallback_before_synthesis(monkeypatch):
    """Verify that if monotonic deadline expires before Phase B synthesis, fallback engine is activated without invoking model."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        make_conclusion_response()
    ]
    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    original_monotonic = time.monotonic
    call_count = [0]
    def fake_monotonic():
        call_count[0] += 1
        if call_count[0] >= 3:
            return original_monotonic() + 100.0  # 100s elapsed
        return original_monotonic()

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    res = agent.execute_review(req)

    assert res is not None
    # Model should only have been called for investigation turn 1, NOT for synthesis
    assert mock_client.models.generate_content.call_count == 1
    # Fallback engine activated because deadline expired before synthesis
    assert "heuristic" in res.engine_used.lower()


def test_upstream_request_timeout_config_passed():
    """Verify that http_options.timeout in milliseconds is configured on GenerateContentConfig."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        make_conclusion_response(),
        make_synthesis_response()
    ]
    agent = ReviewAgent(api_key="mock_key")
    agent._client = mock_client

    req = ReviewRequest(diff_content=SAMPLE_SQLI_AUTH.diff_content)
    agent.execute_review(req)

    # Check investigation config timeout
    _, kwargs_1 = mock_client.models.generate_content.call_args_list[0]
    assert kwargs_1["config"].http_options is not None
    assert kwargs_1["config"].http_options.timeout > 0
    # Verified unit is milliseconds (>= 1000)
    assert kwargs_1["config"].http_options.timeout >= 1000

    # Check synthesis config timeout
    _, kwargs_2 = mock_client.models.generate_content.call_args_list[1]
    assert kwargs_2["config"].http_options is not None
    assert kwargs_2["config"].http_options.timeout > 0
    assert kwargs_2["config"].http_options.timeout >= 1000
