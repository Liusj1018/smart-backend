"""Request/response middleware — trace_id injection and structured logging."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("app")


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Assign a unique trace_id to every request and include it in logs
    and in the response (both success and error)."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id

        start = time.perf_counter()
        logger.info(
            "REQ  %s %s  trace_id=%s",
            request.method,
            request.url.path,
            trace_id,
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                "ERR  %s %s  trace_id=%s  elapsed=%.1fms",
                request.method,
                request.url.path,
                trace_id,
                elapsed,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "RESP %s %s  status=%s  trace_id=%s  elapsed=%.1fms",
            request.method,
            request.url.path,
            response.status_code,
            trace_id,
            elapsed,
        )
        return response


def build_problem_response(
    status: int,
    title: str,
    detail: str,
    instance: str,
    trace_id: str,
) -> JSONResponse:
    """Build an RFC 7807 Problem Details JSON response.

    Uses ``application/problem+json`` as the Content-Type per RFC 7807.
    """
    body = {
        "type": f"https://httpstatuses.com/{status}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        "trace_id": trace_id,
    }
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )
