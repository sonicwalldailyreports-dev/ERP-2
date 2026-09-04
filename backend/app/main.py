import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.audit import reset_audit_context, set_audit_context
from app.core.config import Settings, get_settings
from app.core.dependencies import get_request_id
from app.core.jobs import create_task_queue
from app.db.session import create_engine, create_session_factory

logger = logging.getLogger("small_office")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s] %(message)s")
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Any:
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = correlation_id
        request.state.audit_context_token = set_audit_context(
            request_id=correlation_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled request error")
            raise
        finally:
            reset_audit_context(request.state.audit_context_token)
        response.headers["X-Request-ID"] = correlation_id
        logger.info("%s %s %s %.3fs", request.method, request.url.path, response.status_code, time.perf_counter() - start, extra={"request_id": correlation_id})
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply safe API defaults and small abuse controls at the edge."""

    def __init__(self, app: Any, *, production: bool = False) -> None:
        super().__init__(app)
        self.production = production
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Any:
        try:
            content_length = int(request.headers.get("content-length", "0") or 0)
        except ValueError:
            content_length = 2 * 1024 * 1024 + 1
        if content_length > 2 * 1024 * 1024:
            return JSONResponse(status_code=413, content={"detail": "Request payload is too large."})
        if request.url.path.endswith(("/auth/login", "/auth/password-reset/request")):
            key = (request.client.host if request.client else "-", request.url.path)
            now = time.monotonic()
            bucket = self._requests[key]
            while bucket and bucket[0] <= now - 60:
                bucket.popleft()
            if len(bucket) >= 30:
                return JSONResponse(status_code=429, content={"detail": "Too many requests."})
            bucket.append(now)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def request_id(request: Request) -> str:
    return request.state.request_id


def create_app(
    settings: Settings | None = None,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    app_engine = engine or create_engine(app_settings)
    app_session_factory = session_factory or create_session_factory(app_engine)
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await app_engine.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.engine = app_engine
    application.state.session_factory = app_session_factory
    application.state.task_queue = create_task_queue(app_settings)
    application.add_middleware(SecurityMiddleware, production=app_settings.environment == "production")
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic v2 includes the original ValueError in ``ctx`` for model
        # validators; retaining it makes the error response non-JSON-serializable.
        details = [
            {"loc": error.get("loc", ()), "msg": error.get("msg", "Invalid value"), "type": error.get("type", "value_error")}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.", "details": details}},
            headers={"X-Request-ID": get_request_id(request)},
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, _: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "details": {}}},
            headers={"X-Request-ID": get_request_id(request)},
        )

    application.include_router(api_router, prefix=app_settings.api_prefix)
    return application


app = create_app()
