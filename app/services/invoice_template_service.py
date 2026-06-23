import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import InvoiceTemplate
from app.repositories.invoice_template_repository import InvoiceTemplateRepository
from app.schemas import (
    InvoiceTemplateCreate,
    InvoiceTemplateKind,
    InvoiceTemplateUpdate,
)


def _ensure_valid_payload(template: InvoiceTemplate) -> None:
    if template.kind == InvoiceTemplateKind.built_in:
        if not template.built_in_id:
            raise ValidationError("built_in_id is required for kind=built_in")
        if (
            template.custom_data is not None
            or template.imported_html
            or template.imported_pdf_data_url
        ):
            raise ValidationError("built_in templates cannot include custom/imported data")

    if template.kind == InvoiceTemplateKind.custom:
        if template.custom_data is None:
            raise ValidationError("custom_data is required for kind=custom")
        if template.built_in_id or template.imported_html or template.imported_pdf_data_url:
            raise ValidationError("custom templates cannot include built_in/imported data")

    if template.kind == InvoiceTemplateKind.imported_html:
        if not template.imported_html:
            raise ValidationError("imported_html is required for kind=imported_html")
        if template.built_in_id or template.custom_data is not None or template.imported_pdf_data_url:
            raise ValidationError("imported_html templates cannot include other template data")

    if template.kind == InvoiceTemplateKind.imported_pdf:
        if not template.imported_pdf_data_url:
            raise ValidationError("imported_pdf_data_url is required for kind=imported_pdf")
        if template.built_in_id or template.custom_data is not None or template.imported_html:
            raise ValidationError("imported_pdf templates cannot include other template data")

    if template.kind == InvoiceTemplateKind.imported_excel:
        if template.imported_excel_columns is None:
            raise ValidationError("imported_excel_columns is required for kind=imported_excel")
        if (
            template.built_in_id
            or template.custom_data is not None
            or template.imported_html
            or template.imported_pdf_data_url
        ):
            raise ValidationError("imported_excel templates cannot include other template data")


class InvoiceTemplateService:
    def __init__(self, repo: InvoiceTemplateRepository) -> None:
        self.repo = repo

    async def get_owned(self, template_id: uuid.UUID, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = await self.repo.get(template_id)
        if not template:
            raise NotFoundError("Invoice template not found")
        if template.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return template

    async def list_items(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[InvoiceTemplate], int]:
        return await self.repo.list_by_owner(owner_id, skip=skip, limit=limit)

    async def get_active(self, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = await self.repo.get_active_by_owner(owner_id)
        if not template:
            raise NotFoundError("No active invoice template")
        return template

    async def create(self, template_in: InvoiceTemplateCreate, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = InvoiceTemplate.model_validate(template_in, update={"owner_id": owner_id})
        _ensure_valid_payload(template)

        if template.is_active:
            all_templates = await self.repo.get_all_by_owner(owner_id)
            for t in all_templates:
                if t.is_active:
                    t.is_active = False
                    t.updated_at = get_datetime_utc()
                    self.repo.session.add(t)
            await self.repo.session.flush()

        return await self.repo.add(template)

    async def update(
        self, template_id: uuid.UUID, owner_id: uuid.UUID, template_in: InvoiceTemplateUpdate
    ) -> InvoiceTemplate:
        template = await self.get_owned(template_id, owner_id)
        update_data = template_in.model_dump(exclude_unset=True)

        template.sqlmodel_update(update_data)
        template.updated_at = get_datetime_utc()
        _ensure_valid_payload(template)

        if update_data.get("is_active") is True:
            all_templates = await self.repo.get_all_by_owner(owner_id)
            for t in all_templates:
                if t.id != template.id and t.is_active:
                    t.is_active = False
                    t.updated_at = get_datetime_utc()
                    self.repo.session.add(t)
            await self.repo.session.flush()

        return await self.repo.add(template)

    async def activate(self, template_id: uuid.UUID, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = await self.get_owned(template_id, owner_id)
        all_templates = await self.repo.get_all_by_owner(owner_id)
        now = get_datetime_utc()
        for t in all_templates:
            next_active = t.id == template.id
            if t.is_active != next_active:
                t.is_active = next_active
                t.updated_at = now
                self.repo.session.add(t)
        await self.repo.session.commit()
        await self.repo.session.refresh(template)
        return template

    async def delete(self, template_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        template = await self.get_owned(template_id, owner_id)
        await self.repo.delete(template)
