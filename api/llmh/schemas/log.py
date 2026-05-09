from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class SourceKeyIn(BaseModel):
    hostname: str
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    name: str
    tags: list[str] = Field(default_factory=list)


class LogIngest(BaseModel):
    source_id: uuid.UUID | None = None
    source_key: SourceKeyIn | None = None
    tool: str
    session_id: str | None = None
    idempotency_key: str | None = None
    level: str
    message: str
    raw: dict
    tags: list[str] = Field(default_factory=list)
    occurred_at: datetime

    @model_validator(mode="after")
    def validate_source_selector(self) -> "LogIngest":
        if (self.source_id is None) == (self.source_key is None):
            raise ValueError("exactly one of source_id or source_key is required")
        return self


class LogIngestBatch(BaseModel):
    logs: list[LogIngest]


class IngestResponse(BaseModel):
    ids: list[uuid.UUID]


class LogOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str
    tool: str
    actor: str
    sender: str | None
    session_id: str | None
    idempotency_key: str | None
    level: str
    message: str
    raw: dict
    tags: list[str]
    occurred_at: datetime
    received_at: datetime


class LogsPage(BaseModel):
    items: list[LogOut]
    next_cursor: str | None
    estimated_total: int


class SessionSummary(BaseModel):
    session_id: str
    source_name: str
    tool: str
    log_count: int
    latest_occurred_at: datetime
    preview: str


class SessionSummaryPage(BaseModel):
    items: list[SessionSummary]


def encode_cursor(offset: int) -> str:
    payload = json.dumps({"offset": offset}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        return int(json.loads(raw)["offset"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("invalid cursor") from exc
