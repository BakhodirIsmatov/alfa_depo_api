# RBAC, sessions and audit rollout runbook

This runbook separates release preparation from live proof. A passing local test, isolated PostgreSQL smoke, or image smoke does not prove that production has been migrated.

## 1. Pre-deployment checks

1. Confirm the current database revision and take a recoverable PostgreSQL backup using the platform's normal backup process.
2. Record the API and panel image identifiers currently deployed so they can be restored without rebuilding.
3. Verify that `.env` has a random `JWT_SECRET_KEY` of at least 32 characters and the intended `JWT_ISSUER`, `JWT_AUDIENCE`, `CORS_ORIGINS`, rate limits, and audit bounds. Do not print secrets into CI logs.
4. Run the release gates:

   ```bash
   .venv/bin/ruff check app tests alembic
   .venv/bin/pytest -q
   docker compose config --quiet
   ```

   In the panel checkout run `npm run lint`, `npm run typecheck`, `npm test -- --run`, and `npm run build`.

5. Preview the compatibility backfill before migration:

   ```sql
   SELECT is_admin, count(*) AS users
   FROM users
   GROUP BY is_admin
   ORDER BY is_admin DESC;
   ```

   `is_admin=true` maps to `admin`; every existing `is_admin=false` account maps to `manager`. Confirm that at least one active admin exists.

## 2. Staging or production-like migration

Restore a recent sanitized snapshot into an isolated PostgreSQL instance, then run:

```bash
alembic upgrade head
alembic current
```

The expected head is `20260824_0004`. Validate the result without exposing user data:

```sql
SELECT code, count(u.id) AS users
FROM roles r
LEFT JOIN users u ON u.role_id = r.id
GROUP BY code
ORDER BY code;

SELECT count(*) FROM permissions;

SELECT data_type
FROM information_schema.columns
WHERE table_name = 'audit_events' AND column_name = 'metadata';

SELECT delete_rule
FROM information_schema.referential_constraints
WHERE constraint_name = 'fk_stock_transactions_product_id_products';
```

Expected invariants: four fixed roles, 25 permissions, `audit_events.metadata` as `jsonb`, `users.role_id` non-null, and stock transaction deletion rule `RESTRICT`.

## 3. Deployment order

1. Put a fresh database backup/restore point in place.
2. Apply `alembic upgrade head` once.
3. Deploy the API image and wait for `/health` to become healthy.
4. Run the short-lived seed/sync command once. It synchronizes the fixed roles, permission catalog, and configured admin; it must not log credentials.
5. Deploy the panel build.
6. Keep the transitional `is_admin` response field until every client uses `role` and `effective_permissions`.

Do not run concurrent migration processes. Do not recreate unrelated services as part of verification.

## 4. Role and audit smoke

Use dedicated test accounts; never reuse or disclose a real user's password. Verify:

- `admin`: Users, Roles, Security audit, sessions, Products, Stock, and Reports are accessible.
- `manager`: operational screens work; Users and Security audit return `403 PERMISSION_DENIED`.
- `user`: product/current-stock view and Stock OUT work; product mutation, Stock IN/adjust/history, and Reports return 403.
- `reporter`: report preview/export work. Product/Stock access follows the live role toggles and changes on the next request.
- Logout revokes the current token; password reset, role change, deactivation, and session revoke reject prior tokens with 401.
- Product soft deletion removes it from normal lists but preserves its stock transactions.
- Product, Stock, Report, denied access, login/logout, and permission changes can be found by `request_id` in the correct Operational or Security audit view.
- Every response includes `X-Request-ID`; password, token, Authorization header, cookies, image bytes, and raw OCR images are absent from audit payloads.

## 5. Monitoring

During and after rollout, watch API 401/403/5xx rates, audit insertion failures, session lookup latency, PostgreSQL locks, and audit table/index growth. A sudden 401 increase can indicate issuer/audience or session-version mismatch; a sudden 403 increase can indicate a role matrix error. Product/Stock audited reads and mutations deliberately fail closed if their required audit write cannot commit.

## 6. Rollback

Prefer forward repair if production writes have already entered the new audit/session tables. Rolling the API and panel images back is safe only while the database remains compatible with those older versions. Do not run `alembic downgrade -1` after live RBAC/session/audit activity without first stopping writes and taking another backup: downgrade removes the new history and session data and restores the old cascading stock foreign key.

If migration fails before application deployment, stop the rollout, preserve the error and database logs, restore the pre-migration backup to a separate target, and investigate there. If the API fails after migration, keep the migrated database, restore the prior API only if compatibility is confirmed, and prepare an additive repair migration rather than editing revision `20260824_0004`.

Mark the rollout as live only after the database revision, four-role access matrix, session invalidation, stock ledger, and audit records have been observed in the deployed environment.
