from __future__ import annotations


async def test_admin_can_create_and_update_rule(logged_in_admin):
    create = await logged_in_admin.post(
        "/rules",
        json={
            "name": "auth failures",
            "enabled": True,
            "match_type": "keyword",
            "match_value": "missing token",
            "source_filter": None,
            "tag_filter": None,
            "webhook_url": "https://example.test/hook",
            "email_to": "ops@example.com",
        },
    )
    assert create.status_code == 201
    rule = create.json()
    assert rule["name"] == "auth failures"

    update = await logged_in_admin.patch(f"/rules/{rule['id']}", json={"enabled": False})
    assert update.status_code == 200
    assert update.json()["enabled"] is False


async def test_invalid_regex_rule_rejected(logged_in_admin):
    response = await logged_in_admin.post(
        "/rules",
        json={
            "name": "bad regex",
            "enabled": True,
            "match_type": "regex",
            "match_value": "(",
        },
    )
    assert response.status_code == 422


async def test_viewer_cannot_create_rule(logged_in_viewer):
    response = await logged_in_viewer.post(
        "/rules",
        json={"name": "x", "enabled": True, "match_type": "keyword", "match_value": "x"},
    )
    assert response.status_code == 403
