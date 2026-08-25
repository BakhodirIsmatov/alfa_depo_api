from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.stock_transaction import StockTransaction
from app.schemas.dashboard import DashboardResponse
from app.schemas.product import ProductResponse
from app.schemas.stock import StockTransactionResponse


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> DashboardResponse:
        aggregates = (
            await self.session.execute(
                select(
                    func.count(Product.id),
                    func.coalesce(func.sum(Product.current_stock), 0),
                    func.count(Product.id).filter(Product.current_stock <= Product.minimum_stock),
                    func.count(Product.id).filter(Product.current_stock <= 0),
                ).where(Product.deleted_at.is_(None))
            )
        ).one()
        recent_products = list(
            (
                await self.session.execute(
                    select(Product)
                    .where(Product.deleted_at.is_(None))
                    .order_by(Product.created_at.desc(), Product.id.desc())
                    .limit(5)
                )
            ).scalars()
        )
        recent_transactions = list(
            (
                await self.session.execute(
                    select(StockTransaction)
                    .order_by(StockTransaction.created_at.desc(), StockTransaction.id.desc())
                    .limit(10)
                )
            ).scalars()
        )
        return DashboardResponse(
            total_products=int(aggregates[0]),
            total_stock=Decimal(aggregates[1]),
            low_stock_products=int(aggregates[2]),
            out_of_stock_products=int(aggregates[3]),
            recent_products=[ProductResponse.model_validate(item) for item in recent_products],
            recent_stock_transactions=[
                StockTransactionResponse.model_validate(item) for item in recent_transactions
            ],
        )
