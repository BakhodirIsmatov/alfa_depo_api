from datetime import datetime

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.stock_transaction import StockTransaction
from app.schemas.report import ProductReportFilters, ProductStockStatus

REPORT_SORT_COLUMNS = {
    "product_code": Product.product_code,
    "name": Product.name,
    "brand": Product.brand,
    "color": Product.color,
    "lot_number": Product.lot_number,
    "current_stock": Product.current_stock,
    "minimum_stock": Product.minimum_stock,
    "created_at": Product.created_at,
}


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _product_conditions(
        filters: ProductReportFilters,
        created_start: datetime | None,
        created_end: datetime | None,
    ) -> list:
        conditions = [Product.deleted_at.is_(None)]
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            conditions.append(
                or_(
                    Product.name.ilike(pattern),
                    Product.product_code.ilike(pattern),
                    Product.barcode.ilike(pattern),
                    Product.qr_code.ilike(pattern),
                    Product.brand.ilike(pattern),
                    Product.color.ilike(pattern),
                    Product.lot_number.ilike(pattern),
                    Product.description.ilike(pattern),
                )
            )
        if filters.brand:
            conditions.append(func.lower(Product.brand) == filters.brand.strip().lower())
        if filters.color:
            conditions.append(func.lower(Product.color) == filters.color.strip().lower())
        if filters.lot_number:
            conditions.append(Product.lot_number.ilike(f"%{filters.lot_number.strip()}%"))
        if filters.stock_status == ProductStockStatus.NORMAL:
            conditions.append(Product.current_stock > Product.minimum_stock)
        elif filters.stock_status == ProductStockStatus.LOW:
            conditions.extend(
                (Product.current_stock > 0, Product.current_stock <= Product.minimum_stock)
            )
        elif filters.stock_status == ProductStockStatus.OUT:
            conditions.append(Product.current_stock <= 0)
        if filters.minimum_current_stock is not None:
            conditions.append(Product.current_stock >= filters.minimum_current_stock)
        if filters.maximum_current_stock is not None:
            conditions.append(Product.current_stock <= filters.maximum_current_stock)
        if created_start is not None:
            conditions.append(Product.created_at >= created_start)
        if created_end is not None:
            conditions.append(Product.created_at < created_end)
        return conditions

    async def product_summary(
        self,
        filters: ProductReportFilters,
        created_start: datetime | None,
        created_end: datetime | None,
    ) -> tuple[int, object, object, int, int]:
        conditions = self._product_conditions(filters, created_start, created_end)
        return (
            await self.session.execute(
                select(
                    func.count(Product.id),
                    func.coalesce(func.sum(Product.current_stock), 0),
                    func.coalesce(func.sum(Product.minimum_stock), 0),
                    func.count(Product.id).filter(Product.current_stock <= Product.minimum_stock),
                    func.count(Product.id).filter(Product.current_stock <= 0),
                ).where(*conditions)
            )
        ).one()

    async def products(
        self,
        filters: ProductReportFilters,
        created_start: datetime | None,
        created_end: datetime | None,
        *,
        offset: int = 0,
        limit: int,
    ) -> list[Product]:
        conditions = self._product_conditions(filters, created_start, created_end)
        column = REPORT_SORT_COLUMNS[filters.sort_by]
        order = desc(column) if filters.sort_order == "desc" else asc(column)
        result = await self.session.execute(
            select(Product)
            .where(*conditions)
            .order_by(order, Product.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    async def filter_options(self) -> tuple[list[str], list[str]]:
        brands = list(
            (
                await self.session.scalars(
                    select(Product.brand)
                    .where(Product.deleted_at.is_(None), Product.brand.is_not(None))
                    .distinct()
                    .order_by(Product.brand.asc())
                )
            ).all()
        )
        colors = list(
            (
                await self.session.scalars(
                    select(Product.color)
                    .where(Product.deleted_at.is_(None), Product.color.is_not(None))
                    .distinct()
                    .order_by(Product.color.asc())
                )
            ).all()
        )
        return brands, colors

    async def daily_transactions(
        self, period_start: datetime, period_end: datetime
    ) -> list[tuple[StockTransaction, Product]]:
        result = await self.session.execute(
            select(StockTransaction, Product)
            .join(Product, Product.id == StockTransaction.product_id)
            .where(
                StockTransaction.created_at >= period_start,
                StockTransaction.created_at < period_end,
            )
            .order_by(
                StockTransaction.created_at.asc(),
                StockTransaction.id.asc(),
            )
        )
        return list(result.tuples())
