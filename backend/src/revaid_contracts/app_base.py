"""Shared FastAPI setup for the separate analysis and viewer services."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from revaid_contracts.http_errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from revaid_contracts.logging import bind_request_id, clear_request_context

__all__ = ["create_base_app"]


def create_base_app(*, title: str, settings: Any, lifespan_handler: Any) -> FastAPI:
    app = FastAPI(title=title, version="0.1.0", lifespan=lifespan_handler)
    app.state.settings = settings

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers["x-request-id"] = request_id
        return response

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
    return app
