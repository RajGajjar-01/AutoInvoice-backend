import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    InvoiceTemplate,
    InvoiceTemplateCreate,
    InvoiceTemplateKind,
    InvoiceTemplatePublic,
    InvoiceTemplatesPublic,
    InvoiceTemplateUpdate,
    Message,
    get_datetime_utc,
)

router = APIRouter(prefix="/invoice-templates", tags=["invoice-templates"])


def _ensure_valid_payload(template: InvoiceTemplate) -> None:
    if template.kind == InvoiceTemplateKind.built_in:
        if not template.built_in_id:
            raise HTTPException(status_code=422, detail="built_in_id is required for kind=built_in")
        if template.custom_data is not None or template.imported_html or template.imported_pdf_data_url:
            raise HTTPException(status_code=422, detail="built_in templates cannot include custom/imported data")

    if template.kind == InvoiceTemplateKind.custom:
        if template.custom_data is None:
            raise HTTPException(status_code=422, detail="custom_data is required for kind=custom")
        if template.built_in_id or template.imported_html or template.imported_pdf_data_url:
            raise HTTPException(status_code=422, detail="custom templates cannot include built_in/imported data")

    if template.kind == InvoiceTemplateKind.imported_html:
        if not template.imported_html:
            raise HTTPException(status_code=422, detail="imported_html is required for kind=imported_html")
        if template.built_in_id or template.custom_data is not None or template.imported_pdf_data_url:
            raise HTTPException(status_code=422, detail="imported_html templates cannot include other template data")

    if template.kind == InvoiceTemplateKind.imported_pdf:
        if not template.imported_pdf_data_url:
            raise HTTPException(status_code=422, detail="imported_pdf_data_url is required for kind=imported_pdf")
        if template.built_in_id or template.custom_data is not None or template.imported_html:
            raise HTTPException(status_code=422, detail="imported_pdf templates cannot include other template data")


@router.get("/", response_model=InvoiceTemplatesPublic)
def read_invoice_templates(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 200
) -> Any:
    base_filter = InvoiceTemplate.owner_id == current_user.id

    count_stmt = select(func.count()).select_from(InvoiceTemplate).where(base_filter)
    count = session.exec(count_stmt).one()

    stmt = (
        select(InvoiceTemplate)
        .where(base_filter)
        .order_by(col(InvoiceTemplate.updated_at).desc())
        .offset(skip)
        .limit(limit)
    )
    data = session.exec(stmt).all()
    return InvoiceTemplatesPublic(data=data, count=count)


@router.get("/active", response_model=InvoiceTemplatePublic)
def read_active_invoice_template(session: SessionDep, current_user: CurrentUser) -> Any:
    stmt = select(InvoiceTemplate).where(
        InvoiceTemplate.owner_id == current_user.id,
        InvoiceTemplate.is_active == True,  # noqa: E712
    )
    t = session.exec(stmt).first()
    if not t:
        raise HTTPException(status_code=404, detail="No active invoice template")
    return t


@router.get("/{id}", response_model=InvoiceTemplatePublic)
def read_invoice_template(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    t = session.get(InvoiceTemplate, id)
    if not t:
        raise HTTPException(status_code=404, detail="Invoice template not found")
    if t.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return t


@router.post("/", response_model=InvoiceTemplatePublic)
def create_invoice_template(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    template_in: InvoiceTemplateCreate,
) -> Any:
    t = InvoiceTemplate.model_validate(template_in, update={"owner_id": current_user.id})
    _ensure_valid_payload(t)

    # If creating an active template, deactivate others first
    if t.is_active:
        stmt = select(InvoiceTemplate).where(InvoiceTemplate.owner_id == current_user.id)
        others = session.exec(stmt).all()
        for o in others:
            if o.is_active:
                o.is_active = False
                o.updated_at = get_datetime_utc()
                session.add(o)

    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@router.put("/{id}", response_model=InvoiceTemplatePublic)
def update_invoice_template(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    template_in: InvoiceTemplateUpdate,
) -> Any:
    t = session.get(InvoiceTemplate, id)
    if not t:
        raise HTTPException(status_code=404, detail="Invoice template not found")
    if t.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = template_in.model_dump(exclude_unset=True)

    # Apply update
    t.sqlmodel_update(update_dict)
    t.updated_at = get_datetime_utc()
    _ensure_valid_payload(t)

    # If toggled active, deactivate others
    if update_dict.get("is_active") is True:
        stmt = select(InvoiceTemplate).where(
            InvoiceTemplate.owner_id == current_user.id,
            InvoiceTemplate.id != t.id,
        )
        others = session.exec(stmt).all()
        for o in others:
            if o.is_active:
                o.is_active = False
                o.updated_at = get_datetime_utc()
                session.add(o)

    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@router.post("/{id}/activate", response_model=InvoiceTemplatePublic)
def activate_invoice_template(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    t = session.get(InvoiceTemplate, id)
    if not t:
        raise HTTPException(status_code=404, detail="Invoice template not found")
    if t.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    stmt = select(InvoiceTemplate).where(InvoiceTemplate.owner_id == current_user.id)
    all_templates = session.exec(stmt).all()
    now = get_datetime_utc()

    for tpl in all_templates:
        next_active = tpl.id == t.id
        if tpl.is_active != next_active:
            tpl.is_active = next_active
            tpl.updated_at = now
            session.add(tpl)

    session.commit()
    session.refresh(t)
    return t


@router.delete("/{id}")
def delete_invoice_template(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Message:
    t = session.get(InvoiceTemplate, id)
    if not t:
        raise HTTPException(status_code=404, detail="Invoice template not found")
    if t.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    session.delete(t)
    session.commit()
    return Message(message="Invoice template deleted successfully")
