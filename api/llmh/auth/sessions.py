from __future__ import annotations

from fastapi import Request

SESSION_USER_KEY = "uid"


def set_session_user(request: Request, user_id: str) -> None:
    request.session[SESSION_USER_KEY] = user_id


def clear_session(request: Request) -> None:
    request.session.clear()


def get_session_user_id(request: Request) -> str | None:
    return request.session.get(SESSION_USER_KEY)

