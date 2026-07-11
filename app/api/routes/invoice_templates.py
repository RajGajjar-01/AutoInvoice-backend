import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.deps import CurrentUser, InvoiceTemplateServiceDep
from app.schemas import (
    InvoiceTemplateCreate,
    InvoiceTemplatePublic,
    InvoiceTemplatesPublic,
    InvoiceTemplateUpdate,
)
from app.utils import parse_excel_file

router = APIRouter(prefix="/invoice-templates", tags=["invoice-templates"])


@router.get("/", response_model=InvoiceTemplatesPublic)
async def read_invoice_templates(
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    skip: int = 0,
    limit: int = 200,
) -> Any:
    templates, count = await invoice_template_service.list_items(
        current_user.id, skip=skip, limit=limit
    )
    return InvoiceTemplatesPublic(data=templates, count=count)


@router.get("/active", response_model=InvoiceTemplatePublic)
async def read_active_invoice_template(
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
) -> Any:
    return await invoice_template_service.get_active(current_user.id)


@router.get("/{id}", response_model=InvoiceTemplatePublic)
async def read_invoice_template(
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    id: uuid.UUID,
) -> Any:
    return await invoice_template_service.get_owned(id, current_user.id)


@router.post("/", response_model=InvoiceTemplatePublic, status_code=201)
async def create_invoice_template(
    *,
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    template_in: InvoiceTemplateCreate,
) -> Any:
    return await invoice_template_service.create(template_in, current_user.id)


@router.put("/{id}", response_model=InvoiceTemplatePublic)
async def update_invoice_template(
    *,
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    id: uuid.UUID,
    template_in: InvoiceTemplateUpdate,
) -> Any:
    return await invoice_template_service.update(id, current_user.id, template_in)


@router.post("/{id}/activate", response_model=InvoiceTemplatePublic)
async def activate_invoice_template(
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    id: uuid.UUID,
) -> Any:
    return await invoice_template_service.activate(id, current_user.id)


@router.delete("/{id}", status_code=204)
async def delete_invoice_template(
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    id: uuid.UUID,
) -> None:
    await invoice_template_service.delete(id, current_user.id)


from pydantic import BaseModel


class ExcelParseResponse(BaseModel):
    columns: list[Any]
    column_mapping: dict[str, int]
    data: list[dict[str, Any]]
    total_rows: int


@router.post("/parse-excel", response_model=ExcelParseResponse)
async def parse_excel_preview(
    _current_user: CurrentUser,
    file: UploadFile = File(...),
) -> Any:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_extensions = [".xlsx", ".xls"]
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)",
        )

    try:
        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file provided")
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")

        result = parse_excel_file(file_content)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return ExcelParseResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error parsing Excel file: {str(e)}"
        )
