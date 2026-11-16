"""
DiffGuard FastAPI Application Entrypoint.
Configures CORS, global exception handlers, and API router.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import router as api_router
from app.tools.security_scanner import redact_sensitive_line

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("diffguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} ({settings.APP_ENV})")
    if settings.GEMINI_API_KEY:
        logger.info(f"Gemini API configured with default model: {settings.GEMINI_MODEL}")
    else:
        logger.info("Gemini API key not found in env. Deterministic heuristic agent active as fallback.")
    yield
    logger.info("Shutting down DiffGuard...")


app = FastAPI(
    title="DiffGuard AI Review API",
    description="Intelligent Git Diff & Pull Request Review Agent Backend",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS setup for Next.js frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    safe_msg = redact_sensitive_line(str(exc)) if settings.DEBUG else "An internal server error occurred while processing the request."
    return JSONResponse(
        status_code=500,
        content={"error": "InternalServerError", "message": safe_msg}
    )

# Mount routes under /api
app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "DiffGuard AI Review Engine is operational.",
        "docs_url": "/docs",
        "api_health": "/api/health"
    }

