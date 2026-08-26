from datetime import datetime
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
from app.schemas.report import (
    ProductReportFilterOptions,
    ProductReportFilters,
    ProductReportResponse,
    ReportFormat,
    ReportLanguage,
)
from app.services.audit import AuditService
from app.services.report import ReportService
from app.services.report_export import export_document, product_report_document

router = APIRouter(prefix="/reports", tags=["Reports"])
ProductReportFiltersDep = Annotated[ProductReportFilters, Depends()]
ReportFormatDep = Annotated[ReportFormat, Query()]
ReportLanguageDep = Annotated[ReportLanguage, Query()]
ReportsView = Annotated[User, Depends(require_permissions(PermissionCode.REPORTS_VIEW))]
ReportsExport = Annotated[User, Depends(require_permissions(PermissionCode.REPORTS_EXPORT))]


@router.get(
    "/products",
    response_model=SuccessResponse[ProductReportResponse],
    summary="Preview filtered product report",
    description=(
        "Return a paginated product report preview and aggregate totals using the same "
        "filters as the export endpoint. Low status excludes out-of-stock products."
    ),
)
async def product_report(
    filters: ProductReportFiltersDep,
    request: Request,
    user: ReportsView,
    session: SessionDep,
) -> SuccessResponse[ProductReportResponse]:
    data = await ReportService(session).product_report(filters)
    await AuditService(session).record_read(
        request,
        user,
        category="REPORT",
        action="PRODUCT_REPORT_VIEWED",
        metadata={"filters": filters, "result_count": len(data.items)},
    )
    return SuccessResponse(data=data)


@router.get(
    "/products/filter-options",
    response_model=SuccessResponse[ProductReportFilterOptions],
    summary="Get product report filter options",
    description="Return distinct product brands and colors for report filter controls.",
)
async def product_report_filter_options(
    request: Request, user: ReportsView, session: SessionDep
) -> SuccessResponse[ProductReportFilterOptions]:
    data = await ReportService(session).product_filter_options()
    await AuditService(session).record_read(
        request,
        user,
        category="REPORT",
        action="REPORT_FILTER_OPTIONS_VIEWED",
        metadata={"brand_count": len(data.brands), "color_count": len(data.colors)},
    )
    return SuccessResponse(data=data)


@router.get(
    "/products/export",
    response_class=Response,
    summary="Export filtered product report",
    description=(
        "Generate the complete filtered report as PDF, PNG, or Excel XLSX. The `xls` "
        "alias intentionally returns modern XLSX content. Export row limits are configured "
        "by environment variables."
    ),
    responses={
        200: {
            "content": {
                "application/pdf": {},
                "image/png": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            }
        }
    },
)
async def export_product_report(
    filters: ProductReportFiltersDep,
    request: Request,
    user: ReportsExport,
    session: SessionDep,
    format: ReportFormatDep = ReportFormat.PDF,
    language: ReportLanguageDep = ReportLanguage.TURKISH,
) -> Response:
    settings = get_settings()
    maximum_rows = (
        settings.report_png_max_rows
        if format.normalized == ReportFormat.PNG
        else settings.report_max_export_rows
    )
    service = ReportService(session)
    items, summary = await service.all_product_report_items(filters, maximum_rows=maximum_rows)
    document = product_report_document(
        items,
        summary,
        filters,
        language,
        datetime.now(service.timezone),
    )
    try:
        artifact = await to_thread.run_sync(partial(export_document, document, format))
    except ValueError as exc:
        raise AppError("REPORT_TOO_LARGE", str(exc), 422) from exc
    await AuditService(session).record_read(
        request,
        user,
        category="REPORT",
        action="PRODUCT_REPORT_EXPORTED",
        metadata={
            "filters": filters,
            "format": format.normalized,
            "language": language,
            "result_count": len(items),
        },
    )
    return report_response(artifact.content, artifact.media_type, artifact.filename, len(items))
