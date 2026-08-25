# Alfateks Textile Warehouse — Alpha API

Production-oriented Alpha backend for the admin panel and Flutter mobile app. It contains server-side sessions, fixed-role RBAC, users, append-only audit history, products, QR/barcode lookup, stock transactions, dashboard statistics, and operational product/stock reports.

## Run with Docker

Requirements: Docker with Compose.

```bash
cp .env.example .env
# Replace every placeholder password/secret in .env
docker compose up --build
```

The API runs at `http://localhost:8000`. Migrations run automatically before the API starts.

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- Health: `http://localhost:8000/health`

Create or synchronize development seed data from `.env` after PostgreSQL is healthy:

```bash
docker compose run --rm seed
```

The seed command is idempotent. It creates the admin on first run and synchronizes its username, email, full name, active/admin flags, and password on later runs. Seed credentials are injected only into the short-lived `seed` container, not the continuously running API container.

## Local development

Use Python 3.12+, a running PostgreSQL database, and Tesseract with the configured
language packs. The Docker image already includes English, Turkish, Russian, and
Uzbek OCR.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest -q
```

Tests use an isolated SQLite database and do not require Docker or PostgreSQL. Before deployment, also run the Alembic migration against PostgreSQL and an isolated image smoke test as described in [`docs/RBAC_AUDIT_RUNBOOK.md`](docs/RBAC_AUDIT_RUNBOOK.md).

## Authentication

Log in with JSON:

```json
{
  "username": "admin",
  "password": "your-password"
}
```

Send the returned token as `Authorization: Bearer <token>`. Every JWT has an issuer, audience, expiry, unique `jti`, and auth version. Authorization is resolved from the current database role and permissions on every request; JWT claims are not used as the permission source. `/logout` revokes the server-side session. Password reset, role change, account deactivation, and explicit session revocation invalidate active sessions.

The fixed roles are `admin`, `manager`, `user`, and `reporter`. `admin` always has all permissions. Security permissions (`users.*`, `roles.*`, security audit, and session administration) cannot be assigned to non-admin roles. Non-admin role permissions can be changed through the role API and take effect on the next request.

## API surface

All application endpoints use the `/api/v1` prefix and a consistent `{ "success": true, "data": ... }` envelope.

- `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
- Permission-protected user management at `/users`, including password reset, sessions, and auth events
- `GET /roles`, `GET /permissions`, and `GET/PUT /roles/{code}/permissions`
- Operational/security audit queries at `/audit-events` and `/audit-events/{id}`
- Product CRUD at `/products`
- `POST /products/{id}/image` and `DELETE /products/{id}/image`
- `POST /products/ocr/extract` for camera/gallery OCR suggestions
- `GET /products/lookup/{identifier}` for product code, QR, or barcode
- `GET /products/{id}/stock`
- `POST /products/{id}/stock/in`
- `POST /products/{id}/stock/out`
- `POST /products/{id}/stock/adjust`
- `GET /products/{id}/stock/history`
- `GET /dashboard`
- `GET /dashboard/daily?date=YYYY-MM-DD` and `/dashboard/daily/export`
- `GET /reports/products` and `/reports/products/filter-options`
- `GET /reports/products/export?format=pdf|png|xlsx&language=tr|en|uz`

Product creation is transactional and kilogram-only. The backend generates the `ALF-000001`-style product code, QR identifier, and Code128 value from the definitive database identity. Initial stock and every later stock change create a transaction. Stock rows are locked during changes to prevent lost updates in PostgreSQL.

Product deletion is permission-protected soft deletion: normal queries hide the product while the immutable stock ledger and audit history remain intact. The stock foreign key is `RESTRICT`; no Product or Stock hard-delete API is exposed. Product metadata, images, OCR, stock actions, reports, exports, user operations, and audit visibility each have explicit backend permissions. User and security management remain admin-only invariants even if the database mappings are changed incorrectly.

Product images are uploaded separately through `POST /products/{id}/image`, limited by
`MAX_PRODUCT_IMAGE_BYTES`, validated by decoding their real contents, normalized to
WebP, and persisted in the configured media volume. Use
`DELETE /products/{id}/image` to remove an image.

OCR is intentionally assistive: `POST /products/ocr/extract` accepts the same image
formats and returns `fields`, per-field confidence, raw text, and warnings. It never
creates or changes a product. The panel/mobile client must let the user review the
suggestions before submitting the normal product payload. Configure languages and the
execution bound through `OCR_LANGUAGES` and `OCR_TIMEOUT_SECONDS`.

Product reports use the same server-side search, brand, color, lot, stock-status,
quantity-range, created-date, and sorting filters for preview and export. The daily
report calculates opening/closing stock, IN/OUT totals, positive/negative adjustments,
net change, and transaction counts in `REPORT_TIMEZONE`. PDF and XLSX exports are
bounded by `REPORT_MAX_EXPORT_ROWS`; PNG uses the lower `REPORT_PNG_MAX_ROWS` limit to
avoid unbounded bitmap memory. The `xls` query alias returns modern XLSX content.

## Configuration

See `.env.example`. Required production values include `DATABASE_URL`, a random `JWT_SECRET_KEY` of at least 32 characters, and the exact `CORS_ORIGINS`. Review `JWT_ISSUER`, `JWT_AUDIENCE`, session activity throttling, login rate limits, and audit query bounds for the deployment. `ALLOW_NEGATIVE_STOCK` defaults to `false`. Never commit `.env` or real credentials.

Manual migration commands:

```bash
alembic upgrade head
alembic downgrade -1
```

Migration `20260824_0004` is additive and preserves the earlier revisions. Existing admins are mapped to `admin`; existing non-admin users are mapped to `manager` for compatibility. Deploy in this order: database migration, API, permission seed/sync, panel, then role-specific smoke checks. Do not label the release as live until the production checks in the runbook have been observed.
