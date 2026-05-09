from __future__ import annotations

from ipaddress import ip_address

from fastapi import Request


def _normalize_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("cf-connecting-ip")
    normalized = _normalize_ip(forwarded)
    if normalized:
        return normalized

    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        for part in x_forwarded_for.split(","):
            normalized = _normalize_ip(part)
            if normalized:
                return normalized

    if request.client is not None:
        normalized = _normalize_ip(request.client.host)
        if normalized:
            return normalized
        return request.client.host

    return "unknown"
