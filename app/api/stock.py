from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies import SessionDep, require_permissions
from app.core.permissions import PermissionCode
from app.models.stock_transaction import StockTransactionType
from app.models.user import User
from app.schemas.common import PaginatedData, SuccessResponse
from app.schemas.stock import (
    StockAdjustmentRequest,
    StockChangeRequest,
    StockResponse,
    StockTransactionResponse,
)
from app.services.audit import AuditService
from app.services.stock import StockService

router = APIRouter(prefix="/products/{product_id}/stock", tags=["Stock"])
StockView = Annotated[User, Depends(require_permissions(PermissionCode.STOCK_VIEW))]
StockHistoryView = Annotated[User, Depends(require_permissions(PermissionCode.STOCK_HISTORY_VIEW))]
StockIn = Annotated[User, Depends(require_permissions(PermissionCode.STOCK_IN))]
StockOut = Annotated[User, Depends(require_permissions(PermissionCode.STOCK_OUT))]
StockAdjust = Annotated[User, Depends(require_permissions(PermissionCode.STOCK_ADJUST))]


@router.get(
    "",
    response_model=SuccessResponse[StockResponse],
    summary="Get product stock",
    description="Return current stock, unit, minimum stock, and stock status.",
)
async def get_stock(
    product_id: int, request: Request, user: StockView, session: SessionDep
) -> SuccessResponse[StockResponse]:
    data = await StockService(session).get(product_id)
    await AuditService(session).record_read(
        request,
        user,
        category="STOCK",
        action="STOCK_VIEWED",
        resource_type="product",
        resource_id=product_id,
        resource_label=data.product_code,
    )
    return SuccessResponse(data=data)


async def _change_stock(
    product_id: int,
    payload: StockChangeRequest,
    transaction_type: StockTransactionType,
    user: User,
    session: SessionDep,
    request: Request,
) -> SuccessResponse[StockTransactionResponse]:
    transaction = await StockService(session).change(
        product_id, transaction_type, payload.quantity, payload.note, user, request
    )
    return SuccessResponse(data=StockTransactionResponse.model_validate(transaction))


@router.post(
    "/in",
    response_model=SuccessResponse[StockTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Receive stock",
    description="Increase current stock and write an IN transaction.",
)
async def stock_in(
    product_id: int,
    payload: StockChangeRequest,
    request: Request,
    user: StockIn,
    session: SessionDep,
) -> SuccessResponse[StockTransactionResponse]:
    return await _change_stock(product_id, payload, StockTransactionType.IN, user, session, request)


@router.post(
    "/out",
    response_model=SuccessResponse[StockTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Issue stock",
    description="Decrease current stock and write an OUT transaction.",
)
async def stock_out(
    product_id: int,
    payload: StockChangeRequest,
    request: Request,
    user: StockOut,
    session: SessionDep,
) -> SuccessResponse[StockTransactionResponse]:
    return await _change_stock(
        product_id, payload, StockTransactionType.OUT, user, session, request
    )


@router.post(
    "/adjust",
    response_model=SuccessResponse[StockTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Adjust stock",
    description="Add the entered amount to current stock and write an ADJUSTMENT transaction.",
)
async def adjust_stock(
    product_id: int,
    payload: StockAdjustmentRequest,
    request: Request,
    user: StockAdjust,
    session: SessionDep,
) -> SuccessResponse[StockTransactionResponse]:
    transaction = await StockService(session).change(
        product_id,
        StockTransactionType.ADJUSTMENT,
        payload.quantity,
        payload.note,
        user,
        request,
    )
    return SuccessResponse(data=StockTransactionResponse.model_validate(transaction))


@router.get(
    "/history",
    response_model=SuccessResponse[PaginatedData[StockTransactionResponse]],
    summary="Get stock history",
    description="Return newest-first stock transactions for a product.",
)
async def stock_history(
    product_id: int,
    user: StockHistoryView,
    request: Request,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SuccessResponse[PaginatedData[StockTransactionResponse]]:
    data = await StockService(session).history(product_id, page, page_size)
    await AuditService(session).record_read(
        request,
        user,
        category="STOCK",
        action="STOCK_HISTORY_VIEWED",
        resource_type="product",
        resource_id=product_id,
        metadata={"page": page, "page_size": page_size, "result_count": len(data.items)},
    )
    return SuccessResponse(data=data)
