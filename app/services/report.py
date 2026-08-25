from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import ceil
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.product import Product
from app.models.stock_transaction import StockTransactionType
from app.repositories.report import ReportRepository
from app.schemas.common import PaginationMeta
from app.schemas.report import (
    DailyProductMovement,
    DailyStockReportResponse,
    DailyStockSummary,
    ProductReportFilterOptions,
    ProductReportFilters,
    ProductReportItem,
    ProductReportResponse,
    ProductReportSummary,
)

ZERO = Decimal("0")


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ReportRepository(session)
        settings = get_settings()
        try:
            self.timezone = ZoneInfo(settings.report_timezone)
        except ZoneInfoNotFoundError as exc:
            raise AppError(
                "REPORT_CONFIGURATION_ERROR",
                "Configured report timezone is unavailable",
                500,
            ) from exc
        self.timezone_name = settings.report_timezone

    def _created_period(
        self, filters: ProductReportFilters
    ) -> tuple[datetime | None, datetime | None]:
        if (
            filters.minimum_current_stock is not None
            and filters.maximum_current_stock is not None
            and filters.minimum_current_stock > filters.maximum_current_stock
        ):
            raise AppError(
                "INVALID_REPORT_FILTERS",
                "Minimum current stock cannot exceed maximum current stock",
                422,
            )
        if (
            filters.created_from
            and filters.created_to
            and filters.created_from > filters.created_to
        ):
            raise AppError(
                "INVALID_REPORT_FILTERS",
                "Created-from date cannot be after created-to date",
                422,
            )
        start = (
            datetime.combine(filters.created_from, time.min, self.timezone)
            if filters.created_from
            else None
        )
        end = (
            datetime.combine(filters.created_to + timedelta(days=1), time.min, self.timezone)
            if filters.created_to
            else None
        )
        return start, end

    @staticmethod
    def _stock_status(product: Product) -> str:
        if product.current_stock <= 0:
            return "out"
        if product.current_stock <= product.minimum_stock:
            return "low"
        return "normal"

    def _serialize_product(self, product: Product) -> ProductReportItem:
        return ProductReportItem(
            id=product.id,
            product_code=product.product_code,
            name=product.name,
            brand=product.brand,
            color=product.color,
            color_code=product.color_code,
            lot_number=product.lot_number,
            current_stock=product.current_stock,
            minimum_stock=product.minimum_stock,
            unit="kg",
            stock_status=self._stock_status(product),
            created_at=product.created_at,
        )

    async def product_report(self, filters: ProductReportFilters) -> ProductReportResponse:
        created_start, created_end = self._created_period(filters)
        summary_row = await self.repository.product_summary(filters, created_start, created_end)
        total = int(summary_row[0])
        products = await self.repository.products(
            filters,
            created_start,
            created_end,
            offset=(filters.page - 1) * filters.page_size,
            limit=filters.page_size,
        )
        return ProductReportResponse(
            generated_at=datetime.now(self.timezone),
            timezone=self.timezone_name,
            items=[self._serialize_product(product) for product in products],
            pagination=PaginationMeta(
                page=filters.page,
                page_size=filters.page_size,
                total=total,
                pages=ceil(total / filters.page_size),
            ),
            summary=ProductReportSummary(
                total_products=total,
                total_current_stock=Decimal(summary_row[1]),
                total_minimum_stock=Decimal(summary_row[2]),
                low_stock_products=int(summary_row[3]),
                out_of_stock_products=int(summary_row[4]),
            ),
        )

    async def all_product_report_items(
        self, filters: ProductReportFilters, *, maximum_rows: int
    ) -> tuple[list[ProductReportItem], ProductReportSummary]:
        created_start, created_end = self._created_period(filters)
        summary_row = await self.repository.product_summary(filters, created_start, created_end)
        total = int(summary_row[0])
        if total > maximum_rows:
            raise AppError(
                "REPORT_TOO_LARGE",
                f"Report contains {total} rows; maximum allowed is {maximum_rows}",
                422,
                {"total_rows": total, "maximum_rows": maximum_rows},
            )
        products = await self.repository.products(
            filters,
            created_start,
            created_end,
            limit=maximum_rows + 1,
        )
        summary = ProductReportSummary(
            total_products=total,
            total_current_stock=Decimal(summary_row[1]),
            total_minimum_stock=Decimal(summary_row[2]),
            low_stock_products=int(summary_row[3]),
            out_of_stock_products=int(summary_row[4]),
        )
        return [self._serialize_product(product) for product in products], summary

    async def product_filter_options(self) -> ProductReportFilterOptions:
        brands, colors = await self.repository.filter_options()
        return ProductReportFilterOptions(brands=brands, colors=colors)

    async def daily_stock_report(self, report_date: date | None = None) -> DailyStockReportResponse:
        selected_date = report_date or datetime.now(self.timezone).date()
        period_start = datetime.combine(selected_date, time.min, self.timezone)
        period_end = period_start + timedelta(days=1)
        transactions = await self.repository.daily_transactions(period_start, period_end)

        products: dict[int, dict] = {}
        total_in = ZERO
        total_out = ZERO
        adjustment_in = ZERO
        adjustment_out = ZERO
        for transaction, product in transactions:
            item = products.setdefault(
                product.id,
                {
                    "product_id": product.id,
                    "product_code": product.product_code,
                    "product_name": product.name,
                    "opening_stock": transaction.previous_stock,
                    "closing_stock": transaction.new_stock,
                    "stock_in": ZERO,
                    "stock_out": ZERO,
                    "adjustment_in": ZERO,
                    "adjustment_out": ZERO,
                    "transaction_count": 0,
                },
            )
            item["closing_stock"] = transaction.new_stock
            item["transaction_count"] += 1
            if transaction.transaction_type == StockTransactionType.IN:
                item["stock_in"] += transaction.quantity
                total_in += transaction.quantity
            elif transaction.transaction_type == StockTransactionType.OUT:
                item["stock_out"] += transaction.quantity
                total_out += transaction.quantity
            else:
                difference = transaction.new_stock - transaction.previous_stock
                if difference >= 0:
                    item["adjustment_in"] += difference
                    adjustment_in += difference
                else:
                    absolute = abs(difference)
                    item["adjustment_out"] += absolute
                    adjustment_out += absolute

        movements = [
            DailyProductMovement(
                **item,
                net_change=item["closing_stock"] - item["opening_stock"],
            )
            for item in products.values()
        ]
        movements.sort(key=lambda item: (item.product_code, item.product_id))
        net_change = total_in - total_out + adjustment_in - adjustment_out
        return DailyStockReportResponse(
            report_date=selected_date,
            timezone=self.timezone_name,
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(self.timezone),
            summary=DailyStockSummary(
                stock_in=total_in,
                stock_out=total_out,
                adjustment_in=adjustment_in,
                adjustment_out=adjustment_out,
                net_change=net_change,
                transaction_count=len(transactions),
                affected_products=len(movements),
            ),
            products=movements,
        )
