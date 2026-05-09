from __future__ import annotations

from llmh.auth.reset_tokens import create_reset_token
from llmh.auth.client_ip import get_client_ip
from starlette.requests import Request


async def test_login_and_me(client, admin_user):
    response = await client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert response.status_code == 200
    assert response.json()["username"] == "admin"

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "admin"


async def test_login_rejects_bad_password(client, admin_user):
    response = await client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


async def test_logout_clears_session(client, admin_user):
    login = await client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert login.status_code == 200
    logout = await client.post("/auth/logout")
    assert logout.status_code == 200
    me = await client.get("/auth/me")
    assert me.status_code == 401


async def test_change_password_updates_hash_and_allows_relogin(client, admin_user):
    login = await client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert login.status_code == 200

    change = await client.post("/auth/password", json={"current_password": "secret", "new_password": "secret-123"})
    assert change.status_code == 200
    assert change.json() == {"status": "ok"}

    await client.post("/auth/logout")
    old_login = await client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert old_login.status_code == 401

    relogin = await client.post("/auth/login", json={"username": "admin", "password": "secret-123"})
    assert relogin.status_code == 200


async def test_change_password_rejects_incorrect_current_password(client, admin_user):
    login = await client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert login.status_code == 200

    change = await client.post("/auth/password", json={"current_password": "wrong", "new_password": "secret-123"})
    assert change.status_code == 400
    assert change.json()["detail"] == "current password is incorrect"


async def test_ingest_token_is_admin_only(client, admin_user, viewer_user):
    admin_login = await client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert admin_login.status_code == 200

    token_response = await client.get("/auth/ingest-token")
    assert token_response.status_code == 200
    assert token_response.json()["token"] == "test-ingest-token"

    await client.post("/auth/logout")
    viewer_login = await client.post("/auth/login", json={"username": "viewer", "password": "secret"})
    assert viewer_login.status_code == 200

    viewer_token = await client.get("/auth/ingest-token")
    assert viewer_token.status_code == 403


async def test_reset_password_accepts_valid_token(client, admin_user):
    token = create_reset_token(admin_user)

    reset = await client.post("/auth/reset-password", json={"token": token, "new_password": "secret-456"})
    assert reset.status_code == 200
    assert reset.json() == {"status": "ok"}

    old_login = await client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert old_login.status_code == 401

    new_login = await client.post("/auth/login", json={"username": "admin", "password": "secret-456"})
    assert new_login.status_code == 200


async def test_reset_password_rejects_invalid_token(client):
    reset = await client.post("/auth/reset-password", json={"token": "bad-token", "new_password": "secret-456"})
    assert reset.status_code == 400
    assert reset.json()["detail"] == "invalid reset token"


async def test_login_is_rate_limited_by_ip(client, admin_user):
    for _ in range(10):
        response = await client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert response.status_code == 401

    limited = await client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert limited.status_code == 429
    assert limited.json()["detail"] == "too many requests"


def test_get_client_ip_prefers_cf_connecting_ip() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (b"cf-connecting-ip", b"203.0.113.10"),
            (b"x-forwarded-for", b"198.51.100.5, 198.51.100.6"),
        ],
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "query_string": b"",
        "server": ("testserver", 80),
        "root_path": "",
        "http_version": "1.1",
    }
    request = Request(scope)

    assert get_client_ip(request) == "203.0.113.10"
