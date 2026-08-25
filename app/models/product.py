from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.stock_transaction import StockTransaction
    from app.models.user import User


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("minimum_stock >= 0", name="minimum_stock_nonnegative"),
        CheckConstraint("unit = 'kg'", name="unit_kg_only"),
        Index("ix_products_name_lower", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str] = mapped_column(Text)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    color: Mapped[str] = mapped_column(String(80), index=True)
    color_code: Mapped[str] = mapped_column(String(7))
    unit: Mapped[str] = mapped_column(String(20), default="kg", server_default="kg")
    lot_number: Mapped[str] = mapped_column(String(100), index=True)
    image_url: Mapped[str | None] = mapped_column(String(500))
    qr_code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    barcode: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), server_default="0"
    )
    minimum_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), server_default="0"
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    creator: Mapped["User"] = relationship(
        foreign_keys=[created_by], back_populates="created_products"
    )
    updater: Mapped["User"] = relationship(
        foreign_keys=[updated_by], back_populates="updated_products"
    )
    stock_transactions: Mapped[list["StockTransaction"]] = relationship(back_populates="product")
