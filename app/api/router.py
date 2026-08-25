from fastapi import APIRouter

from app.api import access, audit, auth, dashboard, products, reports, stock, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(access.router)
api_router.include_router(audit.router)
api_router.include_router(users.router)
api_router.include_router(products.router)
api_router.include_router(stock.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)
