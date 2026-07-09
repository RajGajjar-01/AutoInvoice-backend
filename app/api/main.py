from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    company_settings,
    customers,
    google_auth,
    invoice_templates,
    invoices,
    items,
    notifications,
    private,
    tables,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(tables.router)
api_router.include_router(customers.router)
api_router.include_router(invoices.router)
api_router.include_router(invoice_templates.router)
api_router.include_router(company_settings.router)
api_router.include_router(notifications.router)
api_router.include_router(google_auth.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
