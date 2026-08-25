from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class StockTransactionType(StrEnum):
    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"


class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    transaction_type: Mapped[StockTransactionType] = mapped_column(
        Enum(StockTransactionType, name="stock_transaction_type")
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    previous_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    new_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    note: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_username: Mapped[str] = mapped_column(String(50))
    actor_full_name: Mapped[str] = mapped_column(String(120))
    actor_role: Mapped[str] = mapped_column(String(32))
    product_code: Mapped[str] = mapped_column(String(32))
    product_name: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    product: Mapped["Product"] = relationship(back_populates="stock_transactions")
    creator: Mapped["User"] = relationship(back_populates="stock_transactions")
