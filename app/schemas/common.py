from pydantic import BaseModel


class SuccessResponse[T](BaseModel):
    success: bool = True
    data: T


class MessageData(BaseModel):
    message: str


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class PaginatedData[T](BaseModel):
    items: list[T]
    pagination: PaginationMeta


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
