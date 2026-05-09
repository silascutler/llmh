from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RuleBase(BaseModel):
    name: str
    enabled: bool = True
    match_type: str = Field(pattern="^(keyword|regex|source|tag)$")
    match_value: str
    source_filter: uuid.UUID | None = None
    tag_filter: list[str] | None = None
    webhook_url: str | None = None
    email_to: str | None = None

    @field_validator("match_value")
    @classmethod
    def validate_regex(cls, value: str, info) -> str:
        match_type = info.data.get("match_type")
        if match_type == "regex":
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(str(exc)) from exc
        return value


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    match_type: str | None = Field(default=None, pattern="^(keyword|regex|source|tag)$")
    match_value: str | None = None
    source_filter: uuid.UUID | None = None
    tag_filter: list[str] | None = None
    webhook_url: str | None = None
    email_to: str | None = None

    @field_validator("match_value")
    @classmethod
    def validate_regex(cls, value: str | None, info) -> str | None:
        match_type = info.data.get("match_type")
        if value is not None and match_type == "regex":
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(str(exc)) from exc
        return value


class RuleOut(RuleBase):
    id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
