import secrets
import uuid

from app.core.config import settings
from app.core.redis import redis_client
from app.exceptions import RateLimitError, ValidationError

CODE_TTL_SECONDS = settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES * 60
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def _code_key(user_id: uuid.UUID) -> str:
    return f"verify_email:{user_id}"


def _attempts_key(user_id: uuid.UUID) -> str:
    return f"verify_email_attempts:{user_id}"


def _cooldown_key(user_id: uuid.UUID) -> str:
    return f"verify_email_cooldown:{user_id}"


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def issue_code(user_id: uuid.UUID) -> str:
    code = generate_code()
    await redis_client.set(_code_key(user_id), code, ex=CODE_TTL_SECONDS)
    await redis_client.delete(_attempts_key(user_id))
    return code


async def request_resend(user_id: uuid.UUID) -> str:
    reserved = await redis_client.set(
        _cooldown_key(user_id), "1", ex=RESEND_COOLDOWN_SECONDS, nx=True
    )
    if not reserved:
        raise RateLimitError("Please wait before requesting another code")
    return await issue_code(user_id)


async def verify_code(user_id: uuid.UUID, code: str) -> None:
    attempts_key = _attempts_key(user_id)
    attempts = await redis_client.incr(attempts_key)
    if attempts == 1:
        await redis_client.expire(attempts_key, CODE_TTL_SECONDS)
    if attempts > MAX_ATTEMPTS:
        await redis_client.delete(_code_key(user_id))
        raise RateLimitError("Too many incorrect attempts. Please request a new code.")

    stored_code = await redis_client.get(_code_key(user_id))
    if not stored_code or stored_code != code:
        raise ValidationError("Invalid or expired verification code")

    await redis_client.delete(_code_key(user_id))
    await redis_client.delete(attempts_key)
