from datetime import date
from functools import partial
from typing import Annotated

from anyio import to_thread
from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import SessionDep, require_permissions
from app.api.report_utils import report_response
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import PermissionCode
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.dashboard import DashboardResponse
from app.schemas.report import (
    DailyMovementType,
    DailyStockReportResponse,
    ReportFormat,
    ReportLanguage,
)
from app.services.audit import AuditService
from app.services.dashboard import DashboardService
from app.services.report import ReportService
from app.services.report_export import daily_report_document, export_document

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
ReportDateDep = Annotated[date | None, Query(alias="date")]
ReportFormatDep = Annotated[ReportFormat, Query()]
ReportLanguageDep = Annotated[ReportLanguage, Query()]
DailyMovementTypeDep = Annotated[DailyMovementType, Query()]
DashboardView = Annotated[User, Depends(require_permissions(PermissionCode.DASHBOARD_VIEW))]
ReportsView = Annotated[User, Depends(require_permissions(PermissionCode.REPORTS_VIEW))]
ReportsExport = Annotated[User, Depends(require_permissions(PermissionCode.REPORTS_EXPORT))]


@router.get(
    "",
    response_model=SuccessResponse[DashboardResponse],
    summary="Get warehouse dashboard",
    description="Return aggregate stock counts and recent warehouse activity.",
)
async def dashboard(
    request: Request, user: DashboardView, session: SessionDep
) -> SuccessResponse[DashboardResponse]:
    data = await DashboardService(session).get()
    await AuditService(session).record_read(
        request, user, category="DASHBOARD", action="DASHBOARD_VIEWED"
    )
    return SuccessResponse(data=data)


@router.get(
    "/daily",
    response_model=SuccessResponse[DailyStockReportResponse],
    summary="Get daily stock movement report",
    description=(
        "Return stock in, stock out, positive/negative adjustments, net warehouse change, "
        "and per-product opening/closing stock for one reporting-timezone calendar day. "
        "Use movement_type to show all products or only products with inbound/outbound movement."
    ),
)
async def daily_dashboard_report(
    request: Request,
    user: ReportsView,
    session: SessionDep,
    report_date: ReportDateDep = None,
    movement_type: DailyMovementTypeDep = DailyMovementType.ALL,
) -> SuccessResponse[DailyStockReportResponse]:
    data = await ReportService(session).daily_stock_report(report_date, movement_type)
    await AuditService(session).record_read(
        request,
        user,
        category="REPORT",
        action="DAILY_STOCK_REPORT_VIEWED",
        metadata={
            "report_date": data.report_date,
            "movement_type": movement_type,
            "result_count": len(data.products),
        },
    )
    return SuccessResponse(data=data)


@router.get(
    "/daily/export",
    response_class=Response,
    summary="Export daily stock movement report",
    description=(
        "Generate the selected and movement-filtered daily stock report as PDF, PNG, or "
        "Excel XLSX. PNG output is limited to a single A4 landscape canvas."
    ),
)
async def export_daily_dashboard_report(
    request: Request,
    user: ReportsExport,
    session: SessionDep,
    report_date: ReportDateDep = None,
    movement_type: DailyMovementTypeDep = DailyMovementType.ALL,
    format: ReportFormatDep = ReportFormat.PDF,
    language: ReportLanguageDep = ReportLanguage.TURKISH,
) -> Response:
    report = await ReportService(session).daily_stock_report(report_date, movement_type)
    settings = get_settings()
    maximum_rows = (
        settings.report_png_max_rows
        if format.normalized == ReportFormat.PNG
        else settings.report_max_export_rows
    )
    if len(report.products) > maximum_rows:
        raise AppError(
            "REPORT_TOO_LARGE",
            f"Report contains {len(report.products)} rows; maximum allowed is {maximum_rows}",
            422,
        )
    document = daily_report_document(report, language)
    try:
        artifact = await to_thread.run_sync(partial(export_document, document, format))
    except ValueError as exc:
        raise AppError("REPORT_TOO_LARGE", str(exc), 422) from exc
    await AuditService(session).record_read(
        request,
        user,
        category="REPORT",
        action="DAILY_STOCK_REPORT_EXPORTED",
        metadata={
            "report_date": report.report_date,
            "movement_type": movement_type,
            "format": format.normalized,
            "language": language,
            "result_count": len(report.products),
        },
    )
    return report_response(
        artifact.content,
        artifact.media_type,
        artifact.filename,
        len(report.products),
    )
