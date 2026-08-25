from decimal import Decimal

from pydantic import BaseModel

from app.schemas.product import ProductResponse
from app.schemas.stock import StockTransactionResponse


class DashboardResponse(BaseModel):
    total_products: int
    total_stock: Decimal
    low_stock_products: int
    out_of_stock_products: int
    recent_products: list[ProductResponse]
    recent_stock_transactions: list[StockTransactionResponse]
