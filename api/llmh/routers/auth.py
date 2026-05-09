from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.auth.rate_limit import enforce_rate_limit
from llmh.auth.deps import current_user, require_admin
from llmh.auth.reset_tokens import password_fingerprint, read_reset_token
from llmh.config import get_settings
from llmh.auth.passwords import verify_password
from llmh.auth.sessions import clear_session, set_session_user
from llmh.db.models import User
from llmh.db.session import get_session
from llmh.schemas.auth import IngestTokenOut, LoginRequest, PasswordChangeRequest, PasswordResetRequest, UserOut
from llmh.services.users import get_by_username, set_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    await enforce_rate_limit(request, bucket="auth-login", limit=10, window_seconds=60)
    user = await get_by_username(session, body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    set_session_user(request, str(user.id))
    return UserOut.model_validate(user)


@router.post("/logout")
async def logout(request: Request) -> dict[str, str]:
    clear_session(request)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/password")
async def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="new password must be at least 8 characters")
    await set_password(session, user, body.new_password)
    return {"status": "ok"}


@router.post("/reset-password")
async def reset_password(
    body: PasswordResetRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await enforce_rate_limit(request, bucket="auth-reset-password", limit=5, window_seconds=300)
    if len(body.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="new password must be at least 8 characters")
    try:
        token_payload = read_reset_token(body.token, max_age_seconds=60 * 60 * 24)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = await get_by_username(session, token_payload["username"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid reset token")
    if token_payload["password_fingerprint"] != password_fingerprint(user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid reset token")

    await set_password(session, user, body.new_password)
    return {"status": "ok"}


@router.get("/ingest-token", response_model=IngestTokenOut)
async def ingest_token(_: User = Depends(require_admin)) -> IngestTokenOut:
    return IngestTokenOut(token=get_settings().ingest_bearer_token)
