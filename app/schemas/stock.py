from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.stock_transaction import StockTransactionType


class StockChangeRequest(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    count: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class StockAdjustmentRequest(BaseModel):
    quantity: Decimal = Field(max_digits=14, decimal_places=3)
    count: int
    note: str | None = Field(default=None, max_length=500)

    @field_validator("count")
    @classmethod
    def validate_nonzero_count(cls, value: int) -> int:
        if value == 0:
            raise ValueError("count must not be zero")
        return value


class StockTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    transaction_type: StockTransactionType
    quantity: Decimal
    previous_stock: Decimal
    new_stock: Decimal
    count: int | None
    previous_count: int | None
    new_count: int | None
    note: str | None
    created_by: int
    actor_username: str
    actor_full_name: str
    actor_role: str
    product_code: str
    product_name: str
    created_at: datetime


class StockResponse(BaseModel):
    product_id: int
    product_code: str
    current_stock: Decimal
    count: int | None
    minimum_stock: Decimal
    unit: str
    is_low_stock: bool
    is_out_of_stock: bool
