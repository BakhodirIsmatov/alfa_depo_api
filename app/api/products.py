import logging
from functools import partial
from typing import Annotated, Literal

from anyio import to_thread
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status

from app.api.dependencies import SessionDep, require_permissions
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.permissions import PermissionCode
from app.models.user import User
from app.schemas.common import MessageData, PaginatedData, SuccessResponse
from app.schemas.product import (
    ProductCreate,
    ProductLabelTemplateResponse,
    ProductOcrResult,
    ProductResponse,
    ProductUpdate,
)
from app.services.audit import AuditService
from app.services.media import (
    delete_product_image,
    process_product_image,
    store_product_image,
)
from app.services.ocr import extract_product_fields
from app.services.product_label import list_product_label_templates
from app.services.product import ProductService

router = APIRouter(prefix="/products", tags=["Products"])
logger = logging.getLogger(__name__)
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_UNSPECIFIED_IMAGE_TYPES = {"", "application/octet-stream"}
ProductsView = Annotated[User, Depends(require_permissions(PermissionCode.PRODUCTS_VIEW))]
ProductsCreate = Annotated[User, Depends(require_permissions(PermissionCode.PRODUCTS_CREATE))]
ProductsUpdate = Annotated[User, Depends(require_permissions(PermissionCode.PRODUCTS_UPDATE))]
ProductsImage = Annotated[User, Depends(require_permissions(PermissionCode.PRODUCTS_MANAGE_IMAGE))]
ProductsOcr = Annotated[User, Depends(require_permissions(PermissionCode.PRODUCTS_USE_OCR))]
ProductsDelete = Annotated[User, Depends(require_permissions(PermissionCode.PRODUCTS_DELETE))]


async def _read_and_process_image(image: UploadFile):
    content_type = (image.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in _ALLOWED_IMAGE_TYPES | _UNSPECIFIED_IMAGE_TYPES:
        raise AppError("INVALID_IMAGE_TYPE", "Only JPEG, PNG, and WebP images are accepted", 422)
    settings = get_settings()
    content = await image.read(settings.max_product_image_bytes + 1)
    if not content:
        raise AppError("INVALID_IMAGE", "Uploaded image is empty", 422)
    if len(content) > settings.max_product_image_bytes:
        raise AppError("IMAGE_TOO_LARGE", "Product image exceeds the configured size limit", 413)
    processed = await to_thread.run_sync(
        partial(
            process_product_image,
            content,
            max_pixels=settings.max_product_image_pixels,
            max_dimension=settings.product_image_max_dimension,
        )
    )
    return processed


@router.get(
    "",
    response_model=SuccessResponse[PaginatedData[ProductResponse]],
    summary="List products",
    description="Search and paginate products, with allow-listed sorting.",
)
async def list_products(
    user: ProductsView,
    request: Request,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    sort_by: Literal[
        "id", "product_code", "name", "current_stock", "minimum_stock", "created_at", "updated_at"
    ] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> SuccessResponse[PaginatedData[ProductResponse]]:
    data = await ProductService(session).list(page, page_size, search, sort_by, sort_order)
    await AuditService(session).record_read(
        request,
        user,
        category="PRODUCT",
        action="PRODUCT_LIST_VIEWED",
        metadata={
            "page": page,
            "page_size": page_size,
            "search": search,
            "result_count": len(data.items),
        },
    )
    return SuccessResponse(data=data)


@router.post(
    "",
    response_model=SuccessResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
    description="Create a product, generate its internal code/QR, and record initial stock.",
)
async def create_product(
    payload: ProductCreate, request: Request, user: ProductsCreate, session: SessionDep
) -> SuccessResponse[ProductResponse]:
    product = await ProductService(session).create(payload, user, request)
    return SuccessResponse(data=ProductResponse.model_validate(product))


@router.post(
    "/{product_id}/image",
    response_model=SuccessResponse[ProductResponse],
    summary="Upload product image",
    description=(
        "Validate and normalize a JPEG, PNG, or WebP image, replace the product's "
        "previous image, and return the updated product."
    ),
)
async def upload_product_image(
    product_id: int,
    request: Request,
    user: ProductsImage,
    session: SessionDep,
    image: Annotated[UploadFile, File()],
) -> SuccessResponse[ProductResponse]:
    settings = get_settings()
    service = ProductService(session)
    existing = await service.get(product_id)
    old_url = existing.image_url
    processed = await _read_and_process_image(image)
    image_url = await to_thread.run_sync(
        store_product_image, settings.media_root, product_id, processed
    )
    try:
        product = await service.set_image(product_id, image_url, user, request)
    except Exception:
        await to_thread.run_sync(delete_product_image, settings.media_root, image_url)
        raise
    if old_url and old_url != image_url:
        try:
            await to_thread.run_sync(delete_product_image, settings.media_root, old_url)
        except OSError:
            logger.exception("Could not delete replaced product image")
    return SuccessResponse(data=ProductResponse.model_validate(product))


@router.post(
    "/ocr/extract",
    response_model=SuccessResponse[ProductOcrResult],
    summary="Extract product fields from an image",
    description=(
        "Run OCR on a camera/gallery image and return editable field suggestions. "
        "This endpoint never creates or updates a product."
    ),
)
async def extract_product_image_fields(
    user: ProductsOcr,
    request: Request,
    session: SessionDep,
    image: Annotated[UploadFile, File()],
) -> SuccessResponse[ProductOcrResult]:
    settings = get_settings()
    processed = await _read_and_process_image(image)
    result = await to_thread.run_sync(
        partial(
            extract_product_fields,
            processed.content,
            languages=settings.ocr_languages,
            timeout_seconds=settings.ocr_timeout_seconds,
        )
    )
    await AuditService(session).record_read(
        request,
        user,
        category="PRODUCT",
        action="PRODUCT_OCR_USED",
        metadata={"detected_fields": sorted(result.fields.model_dump(exclude_none=True))},
    )
    return SuccessResponse(data=result)


@router.delete(
    "/{product_id}/image",
    response_model=SuccessResponse[ProductResponse],
    summary="Remove product image",
    description="Remove the stored product image and return the updated product.",
)
async def remove_product_image(
    product_id: int, request: Request, user: ProductsImage, session: SessionDep
) -> SuccessResponse[ProductResponse]:
    service = ProductService(session)
    product = await service.get(product_id)
    old_url = product.image_url
    product = await service.set_image(product_id, None, user, request)
    if old_url and old_url.startswith("/media/products/"):
        await to_thread.run_sync(delete_product_image, get_settings().media_root, old_url)
    return SuccessResponse(data=ProductResponse.model_validate(product))


@router.get(
    "/lookup/{identifier}",
    response_model=SuccessResponse[ProductResponse],
    summary="Look up scanned product",
    description="Resolve a product code, QR identifier, or barcode to current product data.",
)
async def lookup_product(
    identifier: str, request: Request, user: ProductsView, session: SessionDep
) -> SuccessResponse[ProductResponse]:
    product = await ProductService(session).lookup(identifier)
    await AuditService(session).record_read(
        request,
        user,
        category="PRODUCT",
        action="PRODUCT_LOOKED_UP",
        resource_type="product",
        resource_id=product.id,
        resource_label=product.product_code,
        metadata={"identifier_type": "scan_identifier"},
    )
    return SuccessResponse(data=ProductResponse.model_validate(product))


@router.get(
    "/label-templates",
    response_model=SuccessResponse[list[ProductLabelTemplateResponse]],
    summary="List supported thermal label templates",
    description=(
        "Return the supported thermal sticker sizes for barcode and QR label generation. "
        "Each template is tuned for mini printers and validated for one identifier per label."
    ),
)
async def product_label_templates(
    request: Request, user: ProductsView, session: SessionDep
) -> SuccessResponse[list[ProductLabelTemplateResponse]]:
    templates = [
        ProductLabelTemplateResponse.model_validate(item, from_attributes=True)
        for item in list_product_label_templates()
    ]
    await AuditService(session).record_read(
        request,
        user,
        category="PRODUCT",
        action="PRODUCT_LABEL_TEMPLATES_VIEWED",
        metadata={"template_count": len(templates)},
    )
    return SuccessResponse(data=templates)


@router.get(
    "/{product_id}",
    response_model=SuccessResponse[ProductResponse],
    summary="Get product",
    description="Return a product and its current stock status.",
)
async def get_product(
    product_id: int, request: Request, user: ProductsView, session: SessionDep
) -> SuccessResponse[ProductResponse]:
    product = await ProductService(session).get(product_id)
    await AuditService(session).record_read(
        request,
        user,
        category="PRODUCT",
        action="PRODUCT_VIEWED",
        resource_type="product",
        resource_id=product.id,
        resource_label=product.product_code,
    )
    return SuccessResponse(data=ProductResponse.model_validate(product))


@router.put(
    "/{product_id}",
    response_model=SuccessResponse[ProductResponse],
    summary="Update product",
    description="Update product metadata. Stock must be changed through stock endpoints.",
)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    request: Request,
    user: ProductsUpdate,
    session: SessionDep,
) -> SuccessResponse[ProductResponse]:
    product = await ProductService(session).update(product_id, payload, user, request)
    return SuccessResponse(data=ProductResponse.model_validate(product))


@router.delete(
    "/{product_id}",
    response_model=SuccessResponse[MessageData],
    summary="Delete product",
    description=("Soft-delete a product while preserving stock and audit history."),
)
async def delete_product(
    product_id: int, request: Request, user: ProductsDelete, session: SessionDep
) -> SuccessResponse[MessageData]:
    service = ProductService(session)
    await service.delete(product_id, user, request)
    return SuccessResponse(data=MessageData(message="Product deleted successfully"))


@router.post(
    "/{product_id}/restore",
    response_model=SuccessResponse[ProductResponse],
    summary="Restore product",
    description="Restore a soft-deleted product without changing its stock ledger.",
)
async def restore_product(
    product_id: int, request: Request, user: ProductsDelete, session: SessionDep
) -> SuccessResponse[ProductResponse]:
    product = await ProductService(session).restore(product_id, user, request)
    return SuccessResponse(data=ProductResponse.model_validate(product))
