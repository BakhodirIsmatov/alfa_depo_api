# USERS, RBAC, audit trail va user activity rejasi

Holat: P0–P6 implementatsiya va release verification 2026-08-24 kuni yakunlangan. P7 production rollout tayyorlangan, lekin live muhitga deploy qilish uchun production vakolati/targeti berilmagani sababli bajarilgan deb belgilanmaydi.

Joriy dalil: backend Ruff va 41 test, panel ESLint/TypeScript va 16 test, panel production build, Compose render, isolated API image/health, toza va `20260821_0003` legacy PostgreSQL migration hamda PostgreSQL API smoke o'tgan. Bu local/isolated dalil production live proof emas. Operator tartibi `docs/RBAC_AUDIT_RUNBOOK.md`da.

Qamrov: `/Users/baxodir/Documents/Works/alfa/api` FastAPI backend va yonidagi `/Users/baxodir/Documents/Works/alfa/panel` React panel

## 1. Maqsad

- Panelga to'liq USERS boshqaruv modulini qo'shish.
- `admin`, `manager`, `user`, `reporter` rollarini joriy qilish.
- Ruxsatlarni faqat backendda tekshiriladigan, admin paneldan boshqariladigan RBAC tizimiga o'tkazish.
- Product, Stock va Report bilan bog'liq barcha amaliyotlarni kim, qachon va nima qilgani bo'yicha o'zgarmas tarixga yozish.
- Loginlar, muvaffaqiyatsiz login urinishlari, logoutlar, sessiyalar, `last_login_at` va `last_activity_at` ma'lumotlarini saqlash.
- Mavjud API envelope, backend-generated product identifikatorlari, kilogram-only contract, row locking va TR-default/EN panel lokalizatsiyasini saqlab qolish.

## 2. Arxitektura bo'yicha qat'iy qarorlar

- Backend yagona authorization manbai bo'ladi. Paneldagi menyu yoki tugmani yashirish xavfsizlik chorasi emas; har bir endpoint permission dependency bilan tekshiriladi.
- To'rtta role fixed/system role bo'ladi. Hozircha custom role yaratish/o'chirish bo'lmaydi; admin faqat non-admin rolelarga biriktirilgan ruxsatlarni boshqaradi.
- `admin` har doim barcha ruxsatlarga ega bo'ladi. Uning asosiy security ruxsatlarini UI yoki API orqali olib tashlab bo'lmaydi.
- `users.*`, `roles.*` va security audit/sessiya boshqaruvi faqat `admin` uchun bo'ladi va boshqa rolelarga grant qilib bo'lmaydi.
- Permission nomlari kodda allow-list sifatida yuritiladi; admin ixtiyoriy, backend tanimaydigan permission string yarata olmaydi.
- JWT ichidagi role/permission authorization uchun ishonchli manba bo'lmaydi. Har bir requestda active user, session va joriy role permissionlari bazadan tekshiriladi.
- Product va user hard-delete qilinmaydi. Soft-delete/deactivate ishlatiladi, chunki tarixiy stock/audit yozuvlari saqlanishi shart.
- `stock_transactions` biznes ledger sifatida saqlanadi va o'zgartirilmaydi. Umumiy `audit_events` esa Product, Stock va Report endpointlarining strukturali tarixini saqlaydi.
- Vaqt bazada UTC `timestamptz` ko'rinishida saqlanadi; panel foydalanuvchi vaqt zonasida ko'rsatadi. Misollardagi `22.08.2026 15:25` kabi qiymatlar UI formatidir.
- Audit matni tarjima qilingan jumla sifatida emas, strukturali event sifatida saqlanadi. Panel undan masalan “A user Alfa productdan 25 kg chiqardi” kartasini TR/EN tilida yasaydi.
- Audit jadvali append-only bo'ladi: application API orqali update/delete endpoint berilmaydi.

## 3. Default role va permission matritsasi

`✓` — default ochiq, `—` — default yopiq, `config` — admin keyinchalik role permission sahifasidan ochib/yopishi mumkin.

| Permission | admin | manager | user | reporter |
| --- | ---: | ---: | ---: | ---: |
| `dashboard.view` | ✓ | ✓ | — | — |
| `products.view` | ✓ | ✓ | ✓ | config (default —) |
| `products.create` | ✓ | ✓ | — | — |
| `products.update` | ✓ | ✓ | — | — |
| `products.manage_image` | ✓ | ✓ | — | — |
| `products.use_ocr` | ✓ | ✓ | — | — |
| `products.delete` | ✓ | ✓ | — | — |
| `stock.view` | ✓ | ✓ | ✓ | config (default —) |
| `stock.history.view` | ✓ | ✓ | — | config (default —) |
| `stock.in` | ✓ | ✓ | — | — |
| `stock.out` | ✓ | ✓ | ✓ | — |
| `stock.adjust` | ✓ | ✓ | — | — |
| `reports.view` | ✓ | ✓ | — | ✓ |
| `reports.export` | ✓ | ✓ | — | ✓ |
| `audit.operations.view` | ✓ | ✓ | — | — |
| `audit.security.view` | ✓ | — | — | — |
| `users.view/create/update/deactivate/reset_password` | ✓ | — | — | — |
| `roles.view/update_permissions` | ✓ | — | — | — |
| `sessions.view/revoke` | ✓ | — | — | — |

Qoida:

- Admin non-admin rolelarning assignable permissionlarini boshqara oladi; jadval yuqoridagi xavfsiz default seedni ko'rsatadi.
- `admin` role barcha permissionlarni implicit oladi.
- `manager` USERS/securitydan boshqa barcha operatsion modullar bilan ishlaydi.
- `user` productlarni ko'radi, productning joriy qoldig'ini ko'radi va faqat `stock.out` bajaradi.
- `reporter` default holatda faqat report preview/exportni ko'radi; keyinchalik `products.view`, `stock.view` va `stock.history.view` alohida yoqib/o'chiriladi.
- `stock.out` berilgan role uchun productni aniqlashga yetadigan `products.view` va joriy qoldiqni ko'rishga yetadigan `stock.view` dependencylari ham validatsiya qilinadi.

## 4. Implementatsiya holati

- Fixed role/permission katalogi, DB mapping va request-scoped permission dependency ishlaydi; transitional `is_admin` faqat eski client compatibility uchun response/modelda saqlangan.
- Barcha Product, Stock, Dashboard, Report, USERS, Role, Session va Audit endpointlari aniq permission bilan himoyalangan.
- Server-side session, real logout, auth version invalidation, login rate limit va throttled activity mavjud.
- Product/user soft-delete, stock ledger snapshotlari va `RESTRICT` FK tarixni saqlaydi; product restore ham audit bilan ishlaydi.
- Strukturali, redacted, request-ID bilan bog'langan Operational/Security audit va bounded query API mavjud.
- Panelda permission-aware route/sidebar/actionlar, USERS, Roles va Audit sahifalari TR-default/EN contract bilan mavjud.

## 5. Ma'lumotlar bazasi modeli

### 5.1. Role va permissions

- [x] `roles` jadvali: `id`, unique `code`, `name`, `is_system`, `created_at`, `updated_at`.
- [x] `permissions` jadvali: `id`, unique `code`, `module`, `description`, `is_assignable`, timestamps.
- [x] `role_permissions` jadvali: `role_id`, `permission_id`, `granted_by`, `granted_at`; `(role_id, permission_id)` unique.
- [x] `users.role_id` FK qo'shish; application qatlamida `UserRole` (`admin|manager|user|reporter`) allow-list bilan tekshirish.
- [x] Permission katalogi va default matrixni idempotent seed/sync qilish.
- [x] Noma'lum yoki DBda yo'q permissionni fail-closed qilish.
- [x] Admin role uchun DB mappingga qaram bo'lmagan “all permissions” invariantini saqlash.

### 5.2. User activity va server-side sessiyalar

- [x] `users`ga `last_login_at`, `last_activity_at`, `deleted_at`, `deleted_by` qo'shish.
- [x] Kerak bo'lsa optimistik session invalidation uchun `auth_version` qo'shish.
- [x] `user_sessions` jadvali yaratish:
  - `id/jti`, `user_id`, `issued_at`, `expires_at`, `last_seen_at`;
  - `revoked_at`, `revoked_by`, `revoke_reason`;
  - login IP, sanitized/truncated User-Agent va device/session label;
  - `user_id`, active/revoked state va expiry uchun indexlar.
- [x] `auth_events` jadvali yaratish:
  - `LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT`, `SESSION_REVOKED`, `PASSWORD_CHANGED`, `ACCOUNT_DISABLED`;
  - `user_id` nullable, yuborilgan normalized identity (password hech qachon emas), timestamp, IP, User-Agent, request ID, success/failure reason code;
  - raw token, password, password hash, authorization header va secretlarni hech qachon yozmaslik.
- [x] Muvaffaqiyatli loginda `last_login_at`ni va yangi sessionni bitta transactionda yozish.
- [x] Authenticated biznes requestlarda `last_activity_at`/session `last_seen_at`ni write amplificationni kamaytirish uchun, masalan, ko'pi bilan har 5 daqiqada yangilash; health check, static media va preflight requestlar activity hisoblanmasin.
- [x] Logoutda joriy `jti`ni revoke qilish; deactivate, password reset yoki role almashganda userning barcha active sessiyalarini revoke qilish.

### 5.3. O'zgarmas audit trail

- [x] `audit_events` jadvali yaratish:
  - identity: `id` (UUID yoki bigint), `request_id`, `occurred_at`;
  - actor: nullable `actor_user_id`, `actor_username`, `actor_full_name`, `actor_role` snapshotlari;
  - event: `category`, `action`, `outcome`, `http_method`, `path`, `status_code`;
  - resource: `resource_type`, nullable `resource_id`, inson o'qiydigan `resource_label` snapshoti;
  - data: PostgreSQL `JSONB` `before`, `after`, `changes`, `metadata`;
  - context: IP va sanitized User-Agent;
  - indexlar: `(occurred_at desc)`, actor, category/action, resource type/id, outcome, request ID.
- [x] JSONB qiymatlarini Pydantic/Decimal/datetime-safe serializerdan o'tkazish.
- [x] Audit redaction allow-listini markazlashtirish; password/token/header/image binary/raw OCR image kabi ma'lumotlarni chiqarib tashlash.
- [x] Audit eventni update/delete qiluvchi repository method yoki endpoint yaratmaslik.
- [x] Muvaffaqiyatli Product/Stock mutation va uning audit eventini bitta DB transactionda commit qilish; audit yozilmasa biznes amaliyoti ham commit bo'lmasin.
- [x] Audited Product/Stock read yoki Report preview/export success javobini audit event commit bo'lgandan keyingina qaytarish; audit yozilmasa `503` bilan fail-closed qilish.
- [x] Read/report/security failure eventlarini alohida qisqa transaction bilan yozish va event natijasini `SUCCESS`, `DENIED`, `FAILED` sifatida belgilash.
- [x] Har bir responsega `X-Request-ID` qaytarish va uni audit yozuvi bilan bog'lash.
- [x] Audit retentionni default cheksiz saqlash; keyinchalik o'chirish emas, admin tasdiqlaydigan arxiv/partition siyosati sifatida alohida loyiha qilish.

### 5.4. Product va stock tarixini saqlash

- [x] Productga `deleted_at`, `deleted_by` qo'shib delete endpointni soft-deletega o'tkazish.
- [x] Default product querylar soft-deleted yozuvlarni yashirsin; audit/stock tarixida product name/code snapshoti saqlansin.
- [x] `stock_transactions.product_id` uchun `ON DELETE CASCADE`ni `RESTRICT`ga o'zgartirish; productionda product hard-delete yo'lini yopish.
- [x] Stock transactionni immutable ledger sifatida saqlash; update/delete API bermaslik.
- [x] `StockTransactionResponse`ga actorning `id`, `username`, `full_name`, `role` snapshotini yoki nested actor summaryni qo'shish.
- [x] Product create ichidagi initial stock ham `PRODUCT_CREATED` va `STOCK_IN` sifatida audit qilinsin; ikkalasi bitta transactionda qolsin.
- [x] Product update eventida faqat o'zgargan allow-listed fieldlar before/after ko'rinsin.
- [x] Image upload/remove, OCR ishlatish, lookup, list/detail view va delete/restore eventlari ham yozilsin.

## 6. Migration strategiyasi

- [x] Oldingi `20260820_0001`–`20260821_0003` revisionlarni tahrirlamasdan yangi additive Alembic revision(lar) yaratish.
- [x] 1-bosqichda yangi jadvallar/nullable ustunlarni qo'shish, role/permissionlarni seed qilish va userlarni backfill qilish.
- [x] Compatibility-first mapping: mavjud `is_admin=true` userlar `admin`, mavjud `is_admin=false` userlar hozirgi keng operatsion accessni yo'qotmasligi uchun `manager` bo'lib backfill qilinadi.
- [x] Backfill tugagach `users.role_id`ni `NOT NULL` va FK bilan mustahkamlash.
- [x] Transitional API release davomida `is_admin`ni computed/deprecated response field sifatida saqlash; panel va boshqa clientlar `role/effective_permissions`ga o'tgach alohida migrationda DB ustunini olib tashlash.
- [x] Product soft-delete va stock FK constraint o'zgarishini alohida, tekshiriladigan revisionda qilish.
- [x] Katta audit indexlarini production lock vaqtini hisobga olib yaratish; kerak bo'lsa PostgreSQL-specific online/concurrent rollout rejasini ajratish.
- [x] Upgrade va downgrade pathni bo'sh DBda ham, `20260821_0003`gacha migratsiya qilingan realistik PostgreSQL snapshotda ham sinash.
- [x] SQLite testlar bilan cheklanmaslik; PostgreSQL migration smoke majburiy.

## 7. Backend RBAC implementatsiyasi

- [x] `app/core/permissions.py`da permission enum/catalog va role defaultlarini aniqlash.
- [x] Role/permission repository va service qatlamlarini mavjud modular pattern asosida qo'shish.
- [x] `require_permissions(*codes, match="all")` FastAPI dependency yaratish.
- [x] Bir request ichida permissionlarni qayta-qayta query qilmaslik uchun request-scoped effective permission cache ishlatish.
- [x] Authorization rad etilganda mavjud error envelope bilan `403`, stabil `PERMISSION_DENIED` code va kerakli permissionni safe detailsda qaytarish.
- [x] Har bir protected endpointni aniq permission bilan bog'lash; oddiy `CurrentUser`ni authorization deb qabul qilmaslik.
- [x] Service/repository qatlamidagi xavfli operatsiyalarga route bypass qilinsa ham ishlaydigan invariantlar qo'yish: last admin, self-deactivation, stock row lock, soft-delete.
- [x] Role permission update vaqtida allow-list, admin-only permission va admin invariantlarini tekshirish.
- [x] Role permission update’ni transactionda bajarish va before/after permission setni auditga yozish.
- [x] Effective permissionlar JWTga qotirib qo'yilmasin; role/permission o'zgarishi keyingi requestdan backendda kuchga kirsin.

### Endpoint–permission mapping

- [x] `/auth/me`, `/auth/logout`: active session; alohida biznes permission talab qilinmaydi.
- [x] `/users/**`: tegishli `users.*`; faqat admin invariant.
- [x] `/roles`, `/permissions`, `/roles/{code}/permissions`: `roles.view` yoki `roles.update_permissions`.
- [x] Product list/detail/lookup: `products.view`.
- [x] Product create: `products.create`; update: `products.update`; delete: `products.delete`.
- [x] Product image upload/remove: `products.manage_image`; OCR: `products.use_ocr`.
- [x] Stock current: `stock.view`; history: `stock.history.view`.
- [x] Stock receive: `stock.in`; issue: `stock.out`; adjustment: `stock.adjust`.
- [x] `/dashboard`: `dashboard.view`.
- [x] Daily/product report preview va filter options: `reports.view`.
- [x] Daily/product export: `reports.export` (va zarur bo'lsa `reports.view`).
- [x] Audit list/detail: operational yoki security categoryga qarab `audit.operations.view`/`audit.security.view`.

## 8. USERS va security API contracti

- [x] `UserResponse`ni `role`, `effective_permissions`, `last_login_at`, `last_activity_at`, `deleted_at` bilan kengaytirish; password/hash qaytarmaslik.
- [x] User listga `search`, `role`, `is_active`, activity/login date range, sort va pagination filterlari qo'shish.
- [x] User create/update payloadlarda faqat fixed rolelardan foydalanish.
- [x] Passwordni create vaqtida talab qilish; update vaqtida bo'sh password “o'zgartirma” ma'nosida qolishi, alohida reset action audit qilinishi.
- [x] `DELETE /users/{id}`ni audit-safe soft-delete/deactivate semantikasiga o'tkazish yoki aniq `/deactivate` action bilan almashtirish; hard delete qilmaslik.
- [x] Oxirgi active adminni demote, deactivate yoki delete qilishni bloklash.
- [x] Adminning o'zini deactivate/delete/demote qilishiga mavjud taqiqni role modeliga mos saqlash.
- [x] Concurrent ikki admin update holatida “last admin” invariantini transaction/row lock bilan himoyalash.
- [x] Role, active state yoki password o'zgarganda barcha sessionlarni revoke qilish va sababini auditga yozish.
- [x] `GET /users/{id}/auth-events`, `GET /users/{id}/sessions`, `POST /users/{id}/sessions/revoke` endpointlarini admin-only qo'shish.
- [x] `GET /roles`, `GET /permissions`, `GET/PUT /roles/{code}/permissions` contractlarini qo'shish.
- [x] Permission update uchun to'liq replacement payload + optimistic version/`updated_at` conflict himoyasini ishlatish.

## 9. Product, Stock va Report audit qamrovi

### Product eventlari

- [x] `PRODUCT_LIST_VIEWED`, `PRODUCT_VIEWED`, `PRODUCT_LOOKED_UP`.
- [x] `PRODUCT_CREATED`, `PRODUCT_UPDATED`, `PRODUCT_DELETED`, kelajak uchun `PRODUCT_RESTORED`.
- [x] `PRODUCT_IMAGE_UPLOADED`, `PRODUCT_IMAGE_REMOVED`, `PRODUCT_OCR_USED`.
- [x] Event metadata: product ID/code/name snapshot, o'zgargan fieldlar, lookup identifier turi; image binary/raw secret yozilmaydi.

### Stock eventlari

- [x] `STOCK_VIEWED`, `STOCK_HISTORY_VIEWED`.
- [x] `STOCK_IN`, `STOCK_OUT`, `STOCK_ADJUSTED`.
- [x] Event metadata: product ID/code/name, quantity, unit, previous/new stock, note, transaction ID.
- [x] Misolni strukturali saqlash: actor `A user`, action `STOCK_OUT`, product `Alfa`, quantity `25.000`, unit `kg`, occurred_at UTC; panel lokal vaqtga formatlaydi.
- [x] Stock mutationda mavjud `SELECT ... FOR UPDATE`ni saqlash va auditni o'sha transaction ichida yozish.

### Report eventlari

- [x] `PRODUCT_REPORT_VIEWED`, `PRODUCT_REPORT_EXPORTED`.
- [x] `DAILY_STOCK_REPORT_VIEWED`, `DAILY_STOCK_REPORT_EXPORTED`.
- [x] Filter options kabi yordamchi report accesslarni ham `REPORT_FILTER_OPTIONS_VIEWED` bilan yozish.
- [x] Metadata: normalized filterlar, report sana/timezone, format/language, result row count; generated PDF/PNG/XLSX binarysini auditga saqlamaslik.
- [x] Failed/too-large export va permission deniallarni `FAILED`/`DENIED` outcome bilan qayd qilish.

## 10. Audit query API

- [x] `GET /audit-events` — pagination, newest-first default.
- [x] Filterlar: date range, actor, actor role, category, action, outcome, resource type/id, request ID, search.
- [x] `GET /audit-events/{id}` — before/after/change va request konteksti bilan detail.
- [x] Operatsion va security eventlarni backendda category bo'yicha ajratib authorization qilish; faqat UI tabiga tayanmaslik.
- [x] Actor keyinchalik rename/deactivate qilinsa ham eventdagi snapshot o'zgarmasligini ta'minlash.
- [x] Audit endpointining o'zi uchun recursion yaratmaslik; uning ko'rilishi alohida minimal security event yoki access log siyosati bilan boshqarilsin.
- [x] Max page size, allow-listed sort va bounded date range bilan og'ir querylardan himoyalash.

## 11. Panel implementatsiyasi

### 11.1. Permission-aware shell

- [x] `src/types/api.ts`ga `RoleCode`, `PermissionCode`, kengaytirilgan `User`, session/auth/audit turlarini qo'shish.
- [x] `AuthContext`da `hasPermission`, `hasAnyPermission` helperlarini taqdim etish.
- [x] `PermissionRoute` yaratib direct URL accessni ham tekshirish; 403 uchun lokalizatsiyalangan Access Denied sahifasi.
- [x] Sidebar va quick actionlarni permission bo'yicha filtrlash.
- [x] Login/default redirectni first allowed routega o'tkazish: admin/manager → dashboard, user → products, reporter → reports.
- [x] Product detailda user uchun faqat ko'rish va Stock OUT actionini ko'rsatish; create/edit/delete/image/OCR/in/adjust/history tugmalarini permissionga qarab boshqarish.
- [x] Reporterga product/stock ruxsati yoqilsa menyu va route refreshdan keyin avtomatik ochilishi.
- [x] Backend 403 qaytarsa lokal permission state’ni `/auth/me` orqali yangilash va xavfsiz sahifaga yo'naltirish.

### 11.2. USERS sahifalari

- [x] `/users` list: ism/username/email qidiruvi, role/status filter, last login/activity, pagination va aniq status badge’lari.
- [x] `/users/new`: username, email, full name, fixed role, active state, password/confirm password.
- [x] `/users/:id`: profil, role/status, created/updated, last login/activity, recent loginlar va active sessionlar.
- [x] `/users/:id/edit`: profile/role/status update, alohida password reset, deactivate va session revoke actionlari.
- [x] Destructive actionlar uchun confirm dialog; current/last admin cheklovlarini UI oldindan tushuntirsin, backend esa baribir majburiy tekshirsin.
- [x] Login failure detailda maxfiy ma'lumot ko'rsatmaslik; IP/User-Agentni admin uchun o'qiladigan, bounded formatda ko'rsatish.

### 11.3. Role permission sahifasi

- [x] `/roles` yoki `/users/roles`da role kartalari va modul bo'yicha permission matrix.
- [x] `admin` satri read-only “barcha ruxsatlar” ko'rinishida bo'lsin.
- [x] Admin-only permissionlar non-admin rolelarda disabled va izohli bo'lsin.
- [x] Reporter uchun Product va Stock ko'rish togglelari aniq ko'rsatilsin.
- [x] Save oldidan diff preview, confirm va concurrent update conflict xabari.
- [x] Save bo'lgach permissions query, current auth user va tegishli menu/route state invalidation qilinsin.

### 11.4. Audit tarixi UI

- [x] `/history` yoki `/audit`da Operational va Security tablari.
- [x] Actor, role, modul, action, outcome, product/resource, date range va request ID filterlari.
- [x] Human-readable timeline/table: actor, amal, product/report, miqdor, lokal vaqt, outcome.
- [x] Detail drawerda before/after field diff, stock previous/new, report filters va request metadata.
- [x] Product detailga faqat shu product audit timeline’ini, stock historyga actor nomi/role’ini qo'shish.
- [x] Raw JSONni default ko'rsatmaslik; kerak bo'lsa admin uchun “technical details” ichida sanitized ko'rsatish.
- [x] Barcha yangi TR va EN matnlarni `src/lib/i18n.ts`da markazlashtirish; hardcoded UI string qoldirmaslik.

## 12. Security va maxfiylik

- [x] Password/token/Authorization header/cookie/image binaryni log/audit/exception detailga yozmaslik uchun unit testli redaction layer.
- [x] Failed loginlarni username/email mavjudligini oshkor qilmaydigan bir xil 401 javobi bilan qaytarish.
- [x] Login endpoint uchun IP + identity bo'yicha rate limit/brute-force himoyasini qo'shish; denial eventini auth historyga yozish.
- [x] JWTga unique `jti`, expiry va issuer/audience contractini qo'shish; revoked/expired sessionni rad etish.
- [x] Role/permission endpointlari uchun CSRF emas, bearer token modeliga mos CORS va origin sozlamalarini saqlash.
- [x] Audit IP headerlarini faqat ishonchli reverse proxy konfiguratsiyasida qabul qilish; aks holda socket client IP ishlatish.
- [x] Audit/auth jadvaliga application DB user uchun kerakli minimal grantlar; auditga update/delete grant bermaslik imkonini productionda ko'rib chiqish.
- [x] Export va user listlarda formulalar/CSV injection, unbounded query va PII leakage testlarini qo'shish.

## 13. Test rejasi

### Backend unit/integration

- [x] To'rt role × barcha endpointlar uchun parametrik permission matrix testlari; har bir ruxsatga kamida allow va deny holati.
- [x] Admin barcha endpointlarga kira olishi va admin-only permissionlar boshqa rolelarga grant qilinmasligi.
- [x] Manager USERS/securitydan tashqari barcha operatsion endpointlarga kirishi.
- [x] User faqat product view/current stock/stock out qila olishi; stock in/adjust/history, product mutation va reportlar 403 bo'lishi.
- [x] Reporter default faqat report view/export; admin toggle qilgandan keyin product/stock view ochilishi va qayta yopilganda darhol 403 bo'lishi.
- [x] Inactive/soft-deleted user, revoked/expired session va stale token testlari.
- [x] Last adminni concurrent demote/deactivate qilishga qarshi test.
- [x] Login success/failure/logout/session revoke va `last_login_at` testlari.
- [x] `last_activity_at` throttle chegarasi: interval ichida ortiqcha write yo'q, intervaldan keyin update bor.
- [x] Har bir Product/Stock/Report action uchun to'g'ri audit event, actor snapshot, request ID, timestamp va metadata testlari.
- [x] Mutation rollback bo'lsa audit/stock/productning hammasi rollback; audit insert xatosida mutation commit bo'lmasligi.
- [x] Password/token/redacted field auditga tushmasligi.
- [x] Product soft-delete stock historyni saqlashi; default product listda ko'rinmasligi.
- [x] Stock concurrency/row-lock va Decimal aniqligi regressiya testlari.
- [x] Audit filter, pagination, category authorization va max page size testlari.
- [x] Mavjud auth/product/stock/dashboard/report testlarini yangi permission fixturelar bilan regressiya sifatida saqlash.

### PostgreSQL/migration

- [x] Toza PostgreSQLda `alembic upgrade head`.
- [x] `20260821_0003` holatidagi realist data bilan upgrade; user role backfill countlari va constraintlarni tekshirish.
- [x] Existing non-admin → manager mapping va admin count invariantini SQL smoke orqali tasdiqlash.
- [x] FK `RESTRICT`, JSONB, enum/check, timezone va indexlarni PostgreSQLda tekshirish.
- [x] Migrationdan keyin product/stock/report authenticated smoke; audit yozuvlari haqiqatan yaratilganini DBdan read-only tekshirish.

### Panel

- [x] Permission helper va `PermissionRoute` unit testlari.
- [x] Har role uchun sidebar/default redirect/action visibility testlari.
- [x] Direct forbidden URL → 403 sahifa testi.
- [x] USERS create/edit/deactivate/password/session flows API mock contract testlari.
- [x] Role permission matrix save/diff/conflict testlari.
- [x] Audit list/filter/detail va stock actor rendering testlari.
- [x] TR/EN key parity va hardcoded yangi UI string regression tekshiruvi.
- [x] `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.

### Backend quality gate

- [x] `ruff check .`.
- [x] `pytest -q`.
- [x] `git diff --check` mavjud bo'lsa; API checkout hozir Git repo bo'lmasa file-level diff/review bilan almashtirish.
- [x] Docker/Compose config va isolated image smoke; mavjud xizmatlarni ruxsatsiz restart/recreate qilmaslik.

## 14. Bosqichma-bosqich bajarish tartibi

### P0 — Contract freeze

- [x] Permission katalogi, endpoint mapping, audit event names va response schema’larni yakunlash.
- [x] Existing client compatibility uchun transitional `is_admin` muddatini belgilash.
- [x] Exit: API/panel type contract va role matrix review qilingan.

### P1 — Additive schema va migration

- [x] Role/permission, sessions/auth events, audit events va soft-delete schema.
- [x] Seed/backfill va PostgreSQL migration smoke.
- [x] Exit: eski data yo'qolmasdan `upgrade head` o'tadi, stock history saqlanadi.

### P2 — Auth va RBAC core

- [x] Permission dependency, session-aware JWT, real logout, last login/activity.
- [x] Barcha mavjud endpointlarga permission mapping.
- [x] Exit: parametrik role matrix testlari to'liq o'tadi.

### P3 — Audit infrastructure

- [x] Request context/request ID, redaction, transactional audit writer, audit query API.
- [x] Product/Stock/Report va auth/security eventlari.
- [x] Exit: har bir talab qilingan amaliyotda query qilinadigan audit record mavjud; rollback testlari o'tadi.

### P4 — USERS va role APIs

- [x] User CRUDni role/activity/session bilan kengaytirish.
- [x] Role permission boshqaruvi, last-admin va session revocation invariantlari.
- [x] Exit: faqat admin USERS/securityni boshqara oladi.

### P5 — Panel

- [x] Permission-aware routing/navigation/actions.
- [x] USERS, role permissions, audit/history sahifalari va product/stock timeline integratsiyasi.
- [x] Exit: har bir role uchun UX API huquqlari bilan mos, TR/EN va responsive.

### P6 — Hardening va release verification

- [x] Backend/panel regression, PostgreSQL, migration, Docker isolated smoke va security testlar.
- [x] README/OpenAPI, permission matrix va operator runbookni yangilash.
- [x] Exit: barcha quality gate o'tadi; static/mock va live PostgreSQL/Docker dalillari alohida qayd etiladi.

### P7 — Production rollout

- [ ] Backup va rollback/runbook tayyorlash; migrationni avval staging/production-like PostgreSQLda bajarish.
- [ ] Role backfill preview: nechta admin/manager bo'lishini migrationdan oldin read-only ko'rsatish.
- [ ] Migration deploy → API deploy → panel deploy tartibini saqlash; transitional response sabab rolling compatibilityni buzmaslik.
- [ ] Seed orqali admin/roles/permissions sync; hech qanday credentialni outputga chiqarmaslik.
- [ ] Smoke: to'rt role login, expected 200/403, stock out/in, report export, audit visibility, revoke/logout.
- [ ] Observability: 401/403/5xx, audit insert failure, session lookup latency va audit table growthni kuzatish.
- [ ] Exit: productionda bajarilgan amaliyot audit, stock ledger va user activityda tekshirilgan; faqat shundan keyin live proof deb belgilash.

## 15. Definition of Done

- [x] `admin`, `manager`, `user`, `reporter` rolelari DB va API/panelda bir xil ishlaydi.
- [x] USERS va role permissions faqat admin uchun ochiq.
- [x] Admin barcha ruxsatlarga ega; manager USERS/securitydan boshqa barcha default operatsiyalarga ega.
- [x] User productlarni ko'radi va faqat stock out qiladi.
- [x] Reporter reportlarni ko'radi/export qiladi; product/stock view ruxsatlari admin tomonidan alohida yoqib/o'chiriladi.
- [x] Direct API call panel cheklovini aylanib o'tolmaydi.
- [x] Product/Stock/Report actionlar actor, vaqt, resource, old/new qiymatlar yoki filter/result metadata bilan auditda qoladi.
- [x] Product/user deactivate yoki rename qilinganda oldingi tarix o'zgarmaydi va stock tarixi o'chmaydi.
- [x] Login success/failure, logout/revoke, last login/activity admin uchun ko'rinadi; maxfiy qiymatlar loglanmaydi.
- [x] Real server-side logout va role/password/deactivate session revocation ishlaydi.
- [x] SQLite testlari bilan birga real PostgreSQL migration/smoke, panel lint/typecheck/test/build va isolated Docker tekshiruvlari o'tgan.

## 16. Hozircha scope tashqarisida

- Custom role yaratish/o'chirish.
- User-specific permission override; ruxsatlar role darajasida boshqariladi.
- Multi-warehouse, supplier/customer/order/accounting yoki boshqa enterprise modullar.
- Audit yozuvlarini edit/delete qilish.
- SIEM, external analytics yoki uzoq muddatli cold-storage integratsiyasi; kelajakda append-only eventlardan alohida loyiha sifatida qo'shiladi.
