from math import ceil

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.models.product import Product
from app.models.stock_transaction import StockTransaction, StockTransactionType
from app.models.user import User
from app.repositories.product import ProductRepository
from app.repositories.stock import StockRepository
from app.schemas.common import PaginatedData, PaginationMeta
from app.schemas.stock import StockResponse, StockTransactionResponse
from app.services.audit import AuditService


class StockService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.products = ProductRepository(session)
        self.stock = StockRepository(session)

    async def _get_product(self, product_id: int, *, for_update: bool = False) -> Product:
        product = await self.products.get_by_id(product_id, for_update=for_update)
        if product is None:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")
        return product

    @staticmethod
    def serialize_stock(product: Product) -> StockResponse:
        return StockResponse(
            product_id=product.id,
            product_code=product.product_code,
            current_stock=product.current_stock,
            minimum_stock=product.minimum_stock,
            unit=product.unit,
            is_low_stock=product.current_stock <= product.minimum_stock,
            is_out_of_stock=product.current_stock <= 0,
        )

    async def get(self, product_id: int) -> StockResponse:
        return self.serialize_stock(await self._get_product(product_id))

    async def change(
        self,
        product_id: int,
        transaction_type: StockTransactionType,
        value,
        note: str | None,
        actor: User,
        request: Request,
    ) -> StockTransaction:
        product = await self._get_product(product_id, for_update=True)
        previous = product.current_stock
        if transaction_type == StockTransactionType.IN:
            new_stock = previous + value
            quantity = value
        elif transaction_type == StockTransactionType.OUT:
            new_stock = previous - value
            quantity = value
        else:
            new_stock = value
            quantity = abs(new_stock - previous)
        if new_stock < 0 and not get_settings().allow_negative_stock:
            raise AppError(
                "INSUFFICIENT_STOCK",
                "Stock operation would make current stock negative",
                409,
            )
        product.current_stock = new_stock
        product.updated_by = actor.id
        transaction = StockTransaction(
            product_id=product.id,
            transaction_type=transaction_type,
            quantity=quantity,
            previous_stock=previous,
            new_stock=new_stock,
            note=note,
            created_by=actor.id,
            actor_username=actor.username,
            actor_full_name=actor.full_name,
            actor_role=actor.role.code,
            product_code=product.product_code,
            product_name=product.name,
        )
        self.stock.add(transaction)
        await self.session.flush()
        action = {
            StockTransactionType.IN: "STOCK_IN",
            StockTransactionType.OUT: "STOCK_OUT",
            StockTransactionType.ADJUSTMENT: "STOCK_ADJUSTED",
        }[transaction_type]
        AuditService(self.session).add(
            request,
            actor,
            category="STOCK",
            action=action,
            status_code=201,
            resource_type="product",
            resource_id=product.id,
            resource_label=product.product_code,
            metadata={
                "product_name": product.name,
                "quantity": quantity,
                "unit": product.unit,
                "previous_stock": previous,
                "new_stock": new_stock,
                "note": note,
                "transaction_id": transaction.id,
            },
        )
        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction

    async def history(
        self, product_id: int, page: int, page_size: int
    ) -> PaginatedData[StockTransactionResponse]:
        await self._get_product(product_id)
        transactions, total = await self.stock.history(product_id, page, page_size)
        return PaginatedData(
            items=[StockTransactionResponse.model_validate(item) for item in transactions],
            pagination=PaginationMeta(
                page=page, page_size=page_size, total=total, pages=ceil(total / page_size)
            ),
        )
