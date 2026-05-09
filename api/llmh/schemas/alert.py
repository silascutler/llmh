from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AlertEventOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    rule_name: str
    log_id: uuid.UUID
    log_message: str
    source_name: str
    occurred_at: datetime
    fired_at: datetime
    delivery_status: dict
