"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# On Windows, psycopg async requires SelectorEventLoop (not ProactorEventLoop).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.exceptions import AppError
from app.middleware import TraceIdMiddleware, build_problem_response
from app.routes.auth import router as auth_router
from app.routes.commits import router as commits_router
from app.routes.members import router as members_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    s = get_settings()
    logger.info("Starting %s v%s", s.app_name, s.app_version)
    logger.info("CORS origins: %s", s.cors_origins_list)
    yield
    logger.info("Shutting down %s", s.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    s: Settings = settings or get_settings()

    application = FastAPI(
        title=s.app_name,
        version=s.app_version,
        description="Smart Commit Helper Backend — multi-tenant team & commit management API",
        lifespan=lifespan,
    )

    # --- Middleware (order matters: outermost first) ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    application.add_middleware(TraceIdMiddleware)

    # --- Routes ---
    application.include_router(auth_router, prefix=s.api_prefix)
    application.include_router(members_router, prefix=s.api_prefix)
    application.include_router(commits_router, prefix=s.api_prefix)

    # --- Exception handlers ---
    @application.exception_handler(AppError)
    async def handle_app_error(
        request: Request, exc: AppError
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", "")
        logger.warning(
            "AppError %s at %s: %s (trace_id=%s)",
            exc.status_code,
            request.url.path,
            exc.detail,
            trace_id,
        )
        return build_problem_response(
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=request.url.path,
            trace_id=trace_id,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", "")
        errors = exc.errors()
        detail = errors[0].get("msg", "Validation error") if errors else "Validation error"
        logger.warning(
            "Validation error at %s: %s (trace_id=%s)",
            request.url.path,
            detail,
            trace_id,
        )
        return build_problem_response(
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Validation Error",
            detail=detail,
            instance=request.url.path,
            trace_id=trace_id,
        )

    @application.exception_handler(PydanticValidationError)
    async def handle_pydantic_error(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", "")
        errors = exc.errors()
        detail = errors[0].get("msg", "Validation error") if errors else "Validation error"
        logger.warning(
            "Pydantic validation error at %s: %s (trace_id=%s)",
            request.url.path,
            detail,
            trace_id,
        )
        return build_problem_response(
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Validation Error",
            detail=detail,
            instance=request.url.path,
            trace_id=trace_id,
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Convert Starlette/FastAPI HTTP exceptions (404, 405, etc.) to RFC 7807."""
        trace_id = getattr(request.state, "trace_id", "")
        title_map = {
            404: "Not Found",
            405: "Method Not Allowed",
            401: "Unauthorized",
            403: "Forbidden",
        }
        title = title_map.get(exc.status_code, "HTTP Error")
        detail = exc.detail if isinstance(exc.detail, str) else title
        logger.warning(
            "HTTP %s at %s: %s (trace_id=%s)",
            exc.status_code,
            request.url.path,
            detail,
            trace_id,
        )
        return build_problem_response(
            status=exc.status_code,
            title=title,
            detail=detail,
            instance=request.url.path,
            trace_id=trace_id,
        )

    @application.exception_handler(Exception)
    async def handle_unexpected(
        request: Request, exc: Exception
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", "")
        logger.exception(
            "Unhandled error at %s (trace_id=%s)", request.url.path, trace_id
        )
        return build_problem_response(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="An unexpected error occurred",
            instance=request.url.path,
            trace_id=trace_id,
        )

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
