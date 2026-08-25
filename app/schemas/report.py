from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import PaginationMeta


class ReportFormat(StrEnum):
    PDF = "pdf"
    PNG = "png"
    XLSX = "xlsx"
    XLS = "xls"

    @property
    def normalized(self) -> "ReportFormat":
        return ReportFormat.XLSX if self == ReportFormat.XLS else self


class ReportLanguage(StrEnum):
    TURKISH = "tr"
    ENGLISH = "en"
    UZBEK = "uz"


class ProductStockStatus(StrEnum):
    ALL = "all"
    NORMAL = "normal"
    LOW = "low"
    OUT = "out"


class ProductReportFilters(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    search: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=120)
    color: str | None = Field(default=None, max_length=80)
    lot_number: str | None = Field(default=None, max_length=100)
    stock_status: ProductStockStatus = ProductStockStatus.ALL
    minimum_current_stock: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    maximum_current_stock: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    created_from: date | None = None
    created_to: date | None = None
    sort_by: Literal[
        "product_code",
        "name",
        "brand",
        "color",
        "lot_number",
        "current_stock",
        "minimum_stock",
        "created_at",
    ] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"


class ProductReportItem(BaseModel):
    id: int
    product_code: str
    name: str
    brand: str
    color: str
    color_code: str
    lot_number: str
    current_stock: Decimal
    minimum_stock: Decimal
    unit: Literal["kg"]
    stock_status: Literal["normal", "low", "out"]
    created_at: datetime


class ProductReportSummary(BaseModel):
    total_products: int
    total_current_stock: Decimal
    total_minimum_stock: Decimal
    low_stock_products: int
    out_of_stock_products: int


class ProductReportResponse(BaseModel):
    generated_at: datetime
    timezone: str
    items: list[ProductReportItem]
    pagination: PaginationMeta
    summary: ProductReportSummary


class ProductReportFilterOptions(BaseModel):
    brands: list[str]
    colors: list[str]


class DailyProductMovement(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    opening_stock: Decimal
    closing_stock: Decimal
    stock_in: Decimal
    stock_out: Decimal
    adjustment_in: Decimal
    adjustment_out: Decimal
    net_change: Decimal
    transaction_count: int
    unit: Literal["kg"] = "kg"


class DailyStockSummary(BaseModel):
    stock_in: Decimal
    stock_out: Decimal
    adjustment_in: Decimal
    adjustment_out: Decimal
    net_change: Decimal
    transaction_count: int
    affected_products: int


class DailyStockReportResponse(BaseModel):
    report_date: date
    timezone: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    summary: DailyStockSummary
    products: list[DailyProductMovement]
