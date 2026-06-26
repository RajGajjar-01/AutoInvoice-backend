from pydantic import BaseModel, EmailStr


class SendEmailRequest(BaseModel):
    to_email: EmailStr
    subject: str = ""


class SendWhatsAppRequest(BaseModel):
    to_phone: str


class SendReminderRequest(BaseModel):
    to_phone: str
    days_overdue: int | None = None
