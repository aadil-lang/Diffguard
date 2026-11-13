"""
API Endpoints for DiffGuard.
Exposes REST and SSE streaming endpoints for diff review, sample catalog, and diagnostics.
"""

import asyncio
import json
import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ReviewRequest, ReviewResponse, SampleDiff, ProcessingStage
from app.samples.sample_diffs import ALL_SAMPLES
from app.agent.reviewer_agent import ReviewAgent
from app.config import settings

logger = logging.getLogger("diffguard.api")
router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """Health and status check."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "gemini_api_configured": bool(settings.GEMINI_API_KEY),
        "default_model": settings.GEMINI_MODEL
    }


@router.get("/samples", response_model=List[SampleDiff], tags=["Samples"])
async def list_sample_diffs():
    """Returns curated sample diffs for evaluation and live testing."""
    return ALL_SAMPLES


@router.get("/samples/{sample_id}", response_model=SampleDiff, tags=["Samples"])
async def get_sample_diff(sample_id: str):
    """Retrieve a single sample diff by ID."""
    for s in ALL_SAMPLES:
        if s.id == sample_id:
            return s
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Sample diff '{sample_id}' not found."
    )


@router.post("/review", response_model=ReviewResponse, tags=["Review"])
async def review_diff(request: ReviewRequest):
    """
    Standard synchronous review endpoint.
    Parses unified diff, executes tool checks, synthesizes findings, and returns structured output.
    """
    try:
        agent = ReviewAgent(
            api_key=request.api_key,
            model_name=request.model_name
        )
        response = agent.execute_review(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unexpected error during diff review execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the code diff: {str(e)}"
        )


@router.post("/review/stream", tags=["Review"])
async def stream_review_diff(request: ReviewRequest):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Emits real-time progress events as the agent advances through processing stages,
    terminating with the final structured ReviewResponse payload.
    """
    queue: asyncio.Queue = asyncio.Queue()

    def stage_callback(stage: ProcessingStage):
        queue.put_nowait({"type": "stage_update", "data": stage.model_dump()})

    async def run_review():
        try:
            agent = ReviewAgent(
                api_key=request.api_key,
                model_name=request.model_name
            )
            # Run CPU-bound/blocking agent in threadpool to keep async event loop responsive
            loop = asyncio.get_running_loop()
            result: ReviewResponse = await loop.run_in_executor(
                None,
                agent.execute_review,
                request,
                stage_callback
            )
            await queue.put({"type": "completed", "data": result.model_dump()})
        except ValueError as val_err:
            await queue.put({"type": "error", "data": {"message": str(val_err), "code": 400}})
        except Exception as exc:
            logger.exception("Streaming agent exception")
            await queue.put({"type": "error", "data": {"message": str(exc), "code": 500}})
        finally:
            await queue.put(None)  # Sentinel to close generator

    async def event_generator():
        # Start background agent execution
        task = asyncio.create_task(run_review())
        
        while True:
            event = await queue.get()
            if event is None:
                break
            
            yield {
                "event": event["type"],
                "data": json.dumps(event["data"])
            }
            queue.task_done()
        
        await task

    return EventSourceResponse(event_generator())

