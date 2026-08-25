from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_transaction import StockTransaction


class StockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, transaction: StockTransaction) -> None:
        self.session.add(transaction)

    async def history(
        self, product_id: int, page: int, page_size: int
    ) -> tuple[list[StockTransaction], int]:
        total = int(
            await self.session.scalar(
                select(func.count())
                .select_from(StockTransaction)
                .where(StockTransaction.product_id == product_id)
            )
            or 0
        )
        result = await self.session.execute(
            select(StockTransaction)
            .where(StockTransaction.product_id == product_id)
            .order_by(StockTransaction.created_at.desc(), StockTransaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars()), total
