from math import ceil

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.product import Product
from app.models.stock_transaction import StockTransaction, StockTransactionType
from app.models.user import User
from app.repositories.product import ProductRepository
from app.repositories.stock import StockRepository
from app.schemas.common import PaginatedData, PaginationMeta
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.audit import AuditService, field_changes

_AUDIT_FIELDS = (
    "name",
    "description",
    "brand",
    "color",
    "color_code",
    "unit",
    "lot_number",
    "image_url",
    "minimum_stock",
    "current_stock",
    "count",
)


def _snapshot(product: Product) -> dict:
    return {field: getattr(product, field) for field in _AUDIT_FIELDS}


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.products = ProductRepository(session)
        self.stock = StockRepository(session)

    async def get(self, product_id: int) -> Product:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")
        return product

    async def lookup(self, identifier: str) -> Product:
        normalized = identifier.strip()
        if not normalized:
            raise AppError("INVALID_IDENTIFIER", "Identifier must not be empty", 422)
        product = await self.products.get_by_identifier(normalized)
        if product is None:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Product not found")
        return product

    async def list(
        self,
        page: int,
        page_size: int,
        search: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PaginatedData[ProductResponse]:
        products, total = await self.products.list(
            page=page,
            page_size=page_size,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return PaginatedData(
            items=[ProductResponse.model_validate(product) for product in products],
            pagination=PaginationMeta(
                page=page, page_size=page_size, total=total, pages=ceil(total / page_size)
            ),
        )

    async def create(self, payload: ProductCreate, actor: User, request: Request) -> Product:
        values = payload.model_dump(exclude={"initial_stock", "product_code"})
        manual_code = payload.product_code
        code_conflict, _ = await self.products.identifier_exists(qr_code=manual_code)
        if code_conflict:
            raise ConflictError(
                "PRODUCT_CODE_CONFLICT",
                "Product code conflicts with an existing scan identifier",
            )
        product = Product(
            **values,
            product_code=manual_code,
            qr_code=manual_code,
            barcode=manual_code,
            current_stock=payload.initial_stock,
            created_by=actor.id,
            updated_by=actor.id,
        )
        self.products.add(product)
        try:
            await self.session.flush()
            actor_role = actor.role.code
            if payload.initial_stock > 0:
                initial_transaction = StockTransaction(
                    product_id=product.id,
                    transaction_type=StockTransactionType.IN,
                    quantity=payload.initial_stock,
                    previous_stock=0,
                    new_stock=payload.initial_stock,
                    count=payload.count if payload.count and payload.count > 0 else None,
                    previous_count=0 if payload.count is not None else None,
                    new_count=payload.count,
                    note="Initial stock",
                    created_by=actor.id,
                    actor_username=actor.username,
                    actor_full_name=actor.full_name,
                    actor_role=actor_role,
                    product_code=product.product_code,
                    product_name=product.name,
                )
                self.stock.add(initial_transaction)
                await self.session.flush()
                AuditService(self.session).add(
                    request,
                    actor,
                    category="STOCK",
                    action="STOCK_IN",
                    status_code=201,
                    resource_type="product",
                    resource_id=product.id,
                    resource_label=product.product_code,
                    metadata={
                        "quantity": payload.initial_stock,
                        "unit": product.unit,
                        "previous_stock": 0,
                        "new_stock": payload.initial_stock,
                        "count": initial_transaction.count,
                        "previous_count": initial_transaction.previous_count,
                        "new_count": initial_transaction.new_count,
                        "note": initial_transaction.note,
                        "transaction_id": initial_transaction.id,
                    },
                )
            AuditService(self.session).add(
                request,
                actor,
                category="PRODUCT",
                action="PRODUCT_CREATED",
                status_code=201,
                resource_type="product",
                resource_id=product.id,
                resource_label=product.product_code,
                after=_snapshot(product),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            await self._raise_identifier_conflict(manual_code, manual_code, exc)
        await self.session.refresh(product)
        return product

    async def update(
        self, product_id: int, payload: ProductUpdate, actor: User, request: Request
    ) -> Product:
        product = await self.get(product_id)
        before = _snapshot(product)
        values = payload.model_dump(exclude_unset=True)
        if "product_code" in values:
            product_code = values["product_code"]
            code_conflict, _ = await self.products.identifier_exists(
                qr_code=product_code, exclude_id=product.id
            )
            if code_conflict:
                raise ConflictError(
                    "PRODUCT_CODE_CONFLICT",
                    "Product code conflicts with an existing scan identifier",
                )
            product.qr_code = product_code
            product.barcode = product_code
        for field, value in values.items():
            setattr(product, field, value)
        product.updated_by = actor.id
        after = _snapshot(product)
        AuditService(self.session).add(
            request,
            actor,
            category="PRODUCT",
            action="PRODUCT_UPDATED",
            resource_type="product",
            resource_id=product.id,
            resource_label=product.product_code,
            before=before,
            after=after,
            changes=field_changes(before, after),
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "PRODUCT_CONFLICT", "Product conflicts with an existing record"
            ) from exc
        await self.session.refresh(product)
        return product

    async def delete(self, product_id: int, actor: User, request: Request) -> None:
        product = await self.get(product_id)
        before = _snapshot(product)
        from datetime import UTC, datetime

        product.deleted_at = datetime.now(UTC)
        product.deleted_by = actor.id
        product.updated_by = actor.id
        AuditService(self.session).add(
            request,
            actor,
            category="PRODUCT",
            action="PRODUCT_DELETED",
            resource_type="product",
            resource_id=product.id,
            resource_label=product.product_code,
            before=before,
            after={"deleted_at": product.deleted_at},
        )
        await self.session.commit()

    async def restore(self, product_id: int, actor: User, request: Request) -> Product:
        product = await self.products.get_deleted_by_id(product_id, for_update=True)
        if product is None:
            raise NotFoundError("PRODUCT_NOT_FOUND", "Deleted product not found")
        before = {"deleted_at": product.deleted_at, "deleted_by": product.deleted_by}
        product.deleted_at = None
        product.deleted_by = None
        product.updated_by = actor.id
        AuditService(self.session).add(
            request,
            actor,
            category="PRODUCT",
            action="PRODUCT_RESTORED",
            resource_type="product",
            resource_id=product.id,
            resource_label=product.product_code,
            before=before,
            after={"deleted_at": None, "deleted_by": None},
            changes=field_changes(before, {"deleted_at": None, "deleted_by": None}),
        )
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def set_image(
        self, product_id: int, image_url: str | None, actor: User, request: Request
    ) -> Product:
        product = await self.get(product_id)
        before = {"image_url": product.image_url}
        product.image_url = image_url
        product.updated_by = actor.id
        AuditService(self.session).add(
            request,
            actor,
            category="PRODUCT",
            action="PRODUCT_IMAGE_UPLOADED" if image_url else "PRODUCT_IMAGE_REMOVED",
            resource_type="product",
            resource_id=product.id,
            resource_label=product.product_code,
            before=before,
            after={"image_url": image_url},
            changes=field_changes(before, {"image_url": image_url}),
        )
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def _raise_identifier_conflict(
        self, qr_code: str | None, barcode: str | None, exc: IntegrityError
    ) -> None:
        qr_exists, barcode_exists = await self.products.identifier_exists(
            qr_code=qr_code, barcode=barcode
        )
        if qr_exists:
            raise ConflictError("DUPLICATE_QR_CODE", "QR identifier already exists") from exc
        if barcode_exists:
            raise ConflictError("DUPLICATE_BARCODE", "Barcode already exists") from exc
        raise ConflictError(
            "PRODUCT_CONFLICT", "Product conflicts with an existing record"
        ) from exc
