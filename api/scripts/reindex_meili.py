from __future__ import annotations

import asyncio

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from llmh.db.models import Log
from llmh.db.session import AsyncSessionLocal
from llmh.search.index import clear_index, ensure_index, index_logs


async def reindex() -> None:
    await ensure_index()
    await clear_index()
    async with AsyncSessionLocal() as session:
        batch_size = 1000
        last_received_at = None
        last_id = None
        while True:
            stmt = (
                select(Log)
                .options(selectinload(Log.source))
                .order_by(Log.received_at.asc(), Log.id.asc())
                .limit(batch_size)
            )
            if last_received_at is not None and last_id is not None:
                stmt = stmt.where(
                    or_(
                        Log.received_at > last_received_at,
                        and_(Log.received_at == last_received_at, Log.id > last_id),
                    )
                )
            result = await session.execute(stmt)
            rows = list(result.scalars())
            if not rows:
                break
            await index_logs(rows)
            last_row = rows[-1]
            last_received_at = last_row.received_at
            last_id = last_row.id


def main() -> None:
    asyncio.run(reindex())


if __name__ == "__main__":
    main()
