import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("AUTHENTICATION_REQUIRED", message, 401)


class AuthorizationError(AppError):
    def __init__(self, message: str = "Administrator access required") -> None:
        super().__init__("FORBIDDEN", message, 403)


class PermissionDeniedError(AppError):
    def __init__(self, required: list[str]) -> None:
        super().__init__(
            "PERMISSION_DENIED",
            "You do not have permission to perform this operation",
            403,
            {"required_permissions": required},
        )


class NotFoundError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 404)


class ConflictError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 409)


def error_body(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "error": error}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.details),
        headers=headers,
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "Request validation failed", details),
    )


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    codes = {
        404: "ENDPOINT_NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            codes.get(exc.status_code, "HTTP_ERROR"),
            str(exc.detail),
        ),
        headers=exc.headers,
    )


async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_ERROR", "An unexpected error occurred"),
    )
