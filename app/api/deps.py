import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.db import async_engine
from app.models import User
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_template_repository import InvoiceTemplateRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.table_repository import TableRepository
from app.repositories.user_repository import UserRepository
from app.schemas import TokenPayload
from app.services.company_settings_service import CompanySettingsService
from app.services.customer_service import CustomerService
from app.services.invoice_pdf_service import InvoicePDFService
from app.services.invoice_service import InvoiceService
from app.services.invoice_template_service import InvoiceTemplateService
from app.services.item_service import ItemService
from app.services.notification_service import NotificationService
from app.services.table_service import TableService
from app.services.user_service import UserService
from app.services.whatsapp_service import WhatsAppService

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_token_from_auth_header_or_cookie(
    authorization: Annotated[str | None, Depends(reusable_oauth2)] = None,
    access_token: Annotated[str | None, Cookie()] = None,
) -> str:
    if access_token:
        return access_token

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return authorization


TokenDep = Annotated[str, Depends(get_token_from_auth_header_or_cookie)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    if token_data.sub is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token: missing subject",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token type",
        )

    try:
        user_uuid = uuid.UUID(token_data.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user ID format",
        )

    user = await session.get(User, user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


SuperUserDep = Annotated[User, Depends(get_current_active_superuser)]


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repo)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_item_repository(session: SessionDep) -> ItemRepository:
    return ItemRepository(session)


def get_item_service(
    repo: Annotated[ItemRepository, Depends(get_item_repository)],
) -> ItemService:
    return ItemService(repo)


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]


def get_customer_repository(session: SessionDep) -> CustomerRepository:
    return CustomerRepository(session)


def get_customer_service(
    repo: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> CustomerService:
    return CustomerService(repo)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]


def get_notification_repository(session: SessionDep) -> NotificationRepository:
    return NotificationRepository(session)


def get_notification_service(
    repo: Annotated[NotificationRepository, Depends(get_notification_repository)],
) -> NotificationService:
    return NotificationService(repo)


NotificationServiceDep = Annotated[
    NotificationService, Depends(get_notification_service)
]


def get_company_settings_repository(session: SessionDep) -> CompanySettingsRepository:
    return CompanySettingsRepository(session)


def get_company_settings_service(
    repo: Annotated[
        CompanySettingsRepository, Depends(get_company_settings_repository)
    ],
) -> CompanySettingsService:
    return CompanySettingsService(repo)


CompanySettingsServiceDep = Annotated[
    CompanySettingsService, Depends(get_company_settings_service)
]


def get_table_repository(session: SessionDep) -> TableRepository:
    return TableRepository(session)


def get_table_service(
    repo: Annotated[TableRepository, Depends(get_table_repository)],
) -> TableService:
    return TableService(repo)


TableServiceDep = Annotated[TableService, Depends(get_table_service)]


def get_invoice_template_repository(session: SessionDep) -> InvoiceTemplateRepository:
    return InvoiceTemplateRepository(session)


def get_invoice_template_service(
    repo: Annotated[
        InvoiceTemplateRepository, Depends(get_invoice_template_repository)
    ],
) -> InvoiceTemplateService:
    return InvoiceTemplateService(repo)


InvoiceTemplateServiceDep = Annotated[
    InvoiceTemplateService, Depends(get_invoice_template_service)
]


def get_invoice_repository(session: SessionDep) -> InvoiceRepository:
    return InvoiceRepository(session)


def get_invoice_service(
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    customer_repo: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> InvoiceService:
    return InvoiceService(repo, customer_repo)


InvoiceServiceDep = Annotated[InvoiceService, Depends(get_invoice_service)]


def get_invoice_pdf_service() -> InvoicePDFService:
    return InvoicePDFService()


InvoicePDFServiceDep = Annotated[InvoicePDFService, Depends(get_invoice_pdf_service)]


def get_whatsapp_service() -> WhatsAppService:
    return WhatsAppService()


WhatsAppServiceDep = Annotated[WhatsAppService, Depends(get_whatsapp_service)]
