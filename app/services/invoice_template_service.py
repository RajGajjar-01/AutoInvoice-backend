import uuid

from app.core.time import get_datetime_utc
from app.exceptions import NotFoundError, ValidationError
from app.models import InvoiceTemplate
from app.repositories.base import get_owned
from app.repositories.invoice_template_repository import InvoiceTemplateRepository
from app.schemas import (
    InvoiceTemplateCreate,
    InvoiceTemplateKind,
    InvoiceTemplateUpdate,
)

# Each template kind owns exactly one payload field; all the others must be empty.
_KIND_FIELDS = {
    InvoiceTemplateKind.built_in: "built_in_id",
    InvoiceTemplateKind.custom: "custom_data",
    InvoiceTemplateKind.imported_html: "imported_html",
    InvoiceTemplateKind.imported_pdf: "imported_pdf_data_url",
    InvoiceTemplateKind.imported_excel: "imported_excel_columns",
}


def _ensure_valid_payload(template: InvoiceTemplate) -> None:
    required_field = _KIND_FIELDS.get(template.kind)
    if required_field is None:
        return

    if getattr(template, required_field) in (None, "", False):
        raise ValidationError(
            f"{required_field} is required for kind={template.kind}"
        )

    other_fields = [f for f in _KIND_FIELDS.values() if f != required_field]
    if any(getattr(template, f) not in (None, "", False) for f in other_fields):
        raise ValidationError(
            f"{template.kind} templates cannot include other template data"
        )


class InvoiceTemplateService:
    def __init__(self, repo: InvoiceTemplateRepository) -> None:
        self.repo = repo

    async def get_owned(
        self, template_id: uuid.UUID, owner_id: uuid.UUID
    ) -> InvoiceTemplate:
        return await get_owned(
            self.repo, template_id, owner_id, "Invoice template not found"
        )

    async def list_items(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[InvoiceTemplate], int]:
        return await self.repo.list_by_owner(owner_id, skip=skip, limit=limit)

    async def get_active(self, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = await self.repo.get_active_by_owner(owner_id)
        if not template:
            raise NotFoundError("No active invoice template")
        return template

    async def create(
        self, template_in: InvoiceTemplateCreate, owner_id: uuid.UUID
    ) -> InvoiceTemplate:
        template = InvoiceTemplate.model_validate(
            template_in, update={"owner_id": owner_id}
        )
        _ensure_valid_payload(template)

        if template.is_active:
            await self.repo.deactivate_all_except(owner_id)
            await self.repo.session.flush()

        return await self.repo.add(template)

    async def update(
        self,
        template_id: uuid.UUID,
        owner_id: uuid.UUID,
        template_in: InvoiceTemplateUpdate,
    ) -> InvoiceTemplate:
        template = await self.get_owned(template_id, owner_id)
        update_data = template_in.model_dump(exclude_unset=True)

        template.sqlmodel_update(update_data)
        template.updated_at = get_datetime_utc()
        _ensure_valid_payload(template)

        if update_data.get("is_active") is True:
            await self.repo.deactivate_all_except(owner_id, exclude_id=template.id)
            await self.repo.session.flush()

        return await self.repo.add(template)

    async def activate(
        self, template_id: uuid.UUID, owner_id: uuid.UUID
    ) -> InvoiceTemplate:
        template = await self.get_owned(template_id, owner_id)
        await self.repo.deactivate_all_except(owner_id, exclude_id=template.id)
        template.is_active = True
        template.updated_at = get_datetime_utc()
        await self.repo.session.commit()
        await self.repo.session.refresh(template)
        return template

    async def delete(self, template_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        template = await self.get_owned(template_id, owner_id)
        await self.repo.delete(template)
