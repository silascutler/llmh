from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SourceBase(BaseModel):
    name: str
    hostname: str | None = None
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    notes: str | None = None
    tags: list[str] | None = None


class SourceOut(SourceBase):
    id: uuid.UUID
    log_count: int = 0
    session_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("ip_address", mode="before")
    @classmethod
    def stringify_ip_address(cls, value: str | IPv4Address | IPv6Address | None) -> str | None:
        if value is None:
            return None
        return str(value)


class SourceDetail(SourceOut):
    last_seen_at: datetime | None = None


class SourceStats(BaseModel):
    debug: int = 0
    info: int = 0
    warn: int = 0
    error: int = 0
