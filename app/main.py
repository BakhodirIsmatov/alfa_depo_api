import logging
import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.exceptions import (
    AppError,
    app_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.schemas.common import MessageData, SuccessResponse
from app.services.audit import AuditService

settings = get_settings()
logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0-alpha",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]
if not settings.debug:
    app.add_exception_handler(Exception, unexpected_error_handler)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Report-Row-Count", "X-Request-ID"],
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)
settings.media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request.state.request_id = supplied if _REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if (
        response.status_code >= 400
        and request.url.path.startswith(settings.api_v1_prefix)
        and not request.url.path.startswith(f"{settings.api_v1_prefix}/audit-events")
    ):
        try:
            actor = getattr(request.state, "current_user", None)
            category = (
                "SECURITY"
                if response.status_code in {401, 403}
                or any(
                    segment in request.url.path
                    for segment in ("/auth/", "/users", "/roles", "/permissions")
                )
                else "OPERATION"
            )
            async with AsyncSessionFactory() as audit_session:
                action = _failure_action(request.url.path, response.status_code)
                AuditService(audit_session).add(
                    request,
                    actor,
                    category=category,
                    action=action,
                    outcome="DENIED" if response.status_code in {401, 403} else "FAILED",
                    status_code=response.status_code,
                    metadata={"query_keys": sorted(request.query_params.keys())},
                )
                await audit_session.commit()
        except Exception:
            logger.exception("Could not persist failed request audit event")
    return response


def _failure_action(path: str, status_code: int) -> str:
    if path.endswith("/reports/products/export"):
        return "PRODUCT_REPORT_EXPORTED"
    if path.endswith("/dashboard/daily/export"):
        return "DAILY_STOCK_REPORT_EXPORTED"
    if status_code in {401, 403}:
        return "REQUEST_DENIED"
    return "REQUEST_FAILED"


@app.get(
    "/health",
    response_model=SuccessResponse[MessageData],
    tags=["System"],
    summary="Health check",
)
async def health(_: Request) -> JSONResponse | SuccessResponse[MessageData]:
    return SuccessResponse(data=MessageData(message="ok"))
