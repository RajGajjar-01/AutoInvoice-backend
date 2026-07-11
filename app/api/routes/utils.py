from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic.networks import EmailStr

from app.api.deps import get_current_active_superuser
from app.core.rate_limit import limiter
from app.schemas import Message
from app.services.email_service import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr, background_tasks: BackgroundTasks) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    background_tasks.add_task(
        send_email,
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/")
@limiter.exempt  # type: ignore[untyped-decorator]
async def health_check(request: Request) -> bool:
    _ = request
    return True
