from __future__ import annotations

import hashlib

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from llmh.config import get_settings
from llmh.db.models import User

RESET_PASSWORD_SALT = "llmh-reset-password"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret)


def password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def create_reset_token(user: User) -> str:
    payload = {
        "username": user.username,
        "password_fingerprint": password_fingerprint(user.password_hash),
    }
    return _serializer().dumps(payload, salt=RESET_PASSWORD_SALT)


def read_reset_token(token: str, *, max_age_seconds: int) -> dict[str, str]:
    try:
        payload = _serializer().loads(token, salt=RESET_PASSWORD_SALT, max_age=max_age_seconds)
    except SignatureExpired as exc:
        raise ValueError("reset token expired") from exc
    except BadSignature as exc:
        raise ValueError("invalid reset token") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid reset token")
    username = payload.get("username")
    fingerprint = payload.get("password_fingerprint")
    if not isinstance(username, str) or not isinstance(fingerprint, str):
        raise ValueError("invalid reset token")
    return {"username": username, "password_fingerprint": fingerprint}
