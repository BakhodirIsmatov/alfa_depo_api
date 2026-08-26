from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

StockValue = Decimal


class ProductFields(BaseModel):
    product_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=180)
    lot_number: str = Field(min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=120)
    color: str | None = Field(default=None, max_length=80, exclude=True)
    color_code: str | None = Field(default=None, max_length=32, exclude=True)
    description: str | None = Field(default=None, max_length=5000)
    unit: Literal["kg"] = "kg"
    minimum_stock: StockValue = Field(ge=0, max_digits=14, decimal_places=3)

    @field_validator("product_code", "name", "lot_number", mode="before")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("brand", "color", "color_code", "description", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ProductCreate(ProductFields):
    initial_stock: StockValue = Field(ge=0, max_digits=14, decimal_places=3)


class ProductUpdate(BaseModel):
    product_code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    lot_number: str | None = Field(default=None, min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=120)
    color: str | None = Field(default=None, max_length=80, exclude=True)
    color_code: str | None = Field(default=None, max_length=32, exclude=True)
    description: str | None = Field(default=None, max_length=5000)
    minimum_stock: StockValue | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)

    @field_validator("product_code", "name", "lot_number", mode="before")
    @classmethod
    def strip_required_strings(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("field cannot be null")
        return value.strip() if isinstance(value, str) else value

    @field_validator("brand", "color", "color_code", "description", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_code: str
    name: str
    lot_number: str
    brand: str | None
    description: str | None
    unit: Literal["kg"]
    qr_code: str
    barcode: str
    image_url: str | None
    current_stock: StockValue
    minimum_stock: StockValue
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    @computed_field
    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.minimum_stock

    @computed_field
    @property
    def is_out_of_stock(self) -> bool:
        return self.current_stock <= 0


class ProductOcrFields(BaseModel):
    name: str | None = None
    lot_number: str | None = None
    brand: str | None = None
    description: str | None = None
    initial_stock: StockValue | None = None
    minimum_stock: StockValue | None = None
    unit: Literal["kg"] = "kg"


class ProductOcrResult(BaseModel):
    raw_text: str
    fields: ProductOcrFields
    confidence: dict[str, float]
    warnings: list[str] = Field(default_factory=list)


class ProductLabelTemplateResponse(BaseModel):
    code: str
    kind: Literal["barcode", "qr"]
    width_mm: int = Field(ge=20, le=100)
    height_mm: int = Field(ge=20, le=100)
    title: str
    description: str
    min_module_mm: float = Field(gt=0)
    quiet_zone_mm: float = Field(ge=0)
    recommended: bool = False
