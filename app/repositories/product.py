from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product

SORT_COLUMNS = {
    "id": Product.id,
    "product_code": Product.product_code,
    "name": Product.name,
    "current_stock": Product.current_stock,
    "minimum_stock": Product.minimum_stock,
    "created_at": Product.created_at,
    "updated_at": Product.updated_at,
}


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, product_id: int, *, for_update: bool = False) -> Product | None:
        statement = select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_deleted_by_id(
        self, product_id: int, *, for_update: bool = False
    ) -> Product | None:
        statement = select(Product).where(
            Product.id == product_id, Product.deleted_at.is_not(None)
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> Product | None:
        result = await self.session.execute(
            select(Product).where(
                Product.deleted_at.is_(None),
                or_(
                    Product.product_code == identifier,
                    Product.qr_code == identifier,
                    Product.barcode == identifier,
                ),
            )
        )
        return result.scalar_one_or_none()

    async def identifier_exists(
        self,
        *,
        qr_code: str | None = None,
        barcode: str | None = None,
        exclude_id: int | None = None,
    ) -> tuple[bool, bool]:
        qr_exists = False
        barcode_exists = False
        if qr_code is not None:
            query = select(Product.id).where(
                or_(
                    Product.product_code == qr_code,
                    Product.qr_code == qr_code,
                    Product.barcode == qr_code,
                )
            )
            if exclude_id is not None:
                query = query.where(Product.id != exclude_id)
            qr_exists = (await self.session.scalar(query.limit(1))) is not None
        if barcode is not None:
            query = select(Product.id).where(
                or_(
                    Product.product_code == barcode,
                    Product.qr_code == barcode,
                    Product.barcode == barcode,
                )
            )
            if exclude_id is not None:
                query = query.where(Product.id != exclude_id)
            barcode_exists = (await self.session.scalar(query.limit(1))) is not None
        return qr_exists, barcode_exists

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[Product], int]:
        filters = [Product.deleted_at.is_(None)]
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Product.name.ilike(pattern),
                    Product.product_code.ilike(pattern),
                    Product.barcode.ilike(pattern),
                    Product.qr_code.ilike(pattern),
                    Product.color.ilike(pattern),
                    Product.lot_number.ilike(pattern),
                    Product.brand.ilike(pattern),
                )
            )
        total_query = select(func.count()).select_from(Product).where(*filters)
        total = int(await self.session.scalar(total_query) or 0)
        column = SORT_COLUMNS[sort_by]
        order_expression = desc(column) if sort_order == "desc" else asc(column)
        result = await self.session.execute(
            select(Product)
            .where(*filters)
            .order_by(order_expression, Product.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars()), total

    def add(self, product: Product) -> None:
        self.session.add(product)

    async def delete(self, product: Product) -> None:
        await self.session.delete(product)
