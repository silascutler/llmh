from __future__ import annotations

import asyncio

from sqlalchemy import select

from llmh.db.models import Log
from llmh.db.session import AsyncSessionLocal
from llmh.utils.claude_import import extract_content_text, resolve_level, resolve_sender, summarize_message


async def repair() -> int:
    repaired = 0
    async with AsyncSessionLocal() as session:
        stmt = select(Log).where(Log.tool == "claude-code")
        result = await session.execute(stmt)
        rows = list(result.scalars())
        for row in rows:
            if not isinstance(row.raw, dict):
                continue
            record = row.raw.get("record")
            if not isinstance(record, dict):
                continue
            sender = resolve_sender(record)
            content_text = extract_content_text(record)
            message = summarize_message(record, sender)
            level = resolve_level(record, sender)

            raw = dict(row.raw)
            changed = False
            if raw.get("sender") != sender:
                raw["sender"] = sender
                changed = True
            if raw.get("record_type") != record.get("type"):
                raw["record_type"] = record.get("type")
                changed = True
            attachment_type = record.get("attachment", {}).get("type") if isinstance(record.get("attachment"), dict) else None
            if raw.get("attachment_type") != attachment_type:
                raw["attachment_type"] = attachment_type
                changed = True
            if raw.get("content_text") != content_text:
                raw["content_text"] = content_text
                changed = True
            if row.message != message:
                row.message = message
                changed = True
            if row.level != level:
                row.level = level
                changed = True
            if changed:
                row.raw = raw
                repaired += 1
        await session.commit()
    return repaired


def main() -> None:
    repaired = asyncio.run(repair())
    print(f"repaired {repaired} claude logs")


if __name__ == "__main__":
    main()
