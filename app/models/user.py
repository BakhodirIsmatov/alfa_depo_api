from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.access import Role
    from app.models.product import Product
    from app.models.stock_transaction import StockTransaction


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    role: Mapped["Role"] = relationship(back_populates="users", lazy="selectin")

    created_products: Mapped[list["Product"]] = relationship(
        foreign_keys="Product.created_by", back_populates="creator"
    )
    updated_products: Mapped[list["Product"]] = relationship(
        foreign_keys="Product.updated_by", back_populates="updater"
    )
    stock_transactions: Mapped[list["StockTransaction"]] = relationship(back_populates="creator")
