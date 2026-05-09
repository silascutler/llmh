from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete

from llmh.db.models import AlertEvent, Log, Source
from llmh.db.session import AsyncSessionLocal
from llmh.schemas.source import SourceCreate
from llmh.search.index import clear_index, ensure_index
from llmh.services import sources as source_service
from llmh.services.logs import ingest
from llmh.utils.claude_import import build_log_ingest, find_source_dir, iter_project_files, parse_source_dir


async def clear_archive_state() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AlertEvent))
        await session.execute(delete(Log))
        await session.execute(delete(Source))
        await session.commit()
    await ensure_index()
    await clear_index()


async def ensure_sources(import_root: Path) -> dict[str, str]:
    source_ids: dict[str, str] = {}
    async with AsyncSessionLocal() as session:
        for source_dir in sorted(path for path in import_root.iterdir() if path.is_dir()):
            source_spec = parse_source_dir(source_dir)
            source = await source_service.create_source(
                session,
                SourceCreate(
                    name=source_spec.source_name,
                    hostname=source_spec.ip_address,
                    ip_address=source_spec.ip_address,
                    port=source_spec.port,
                    notes=f"Imported Claude archive source from {source_spec.source_name}",
                    tags=["imported", "claude-archive"],
                ),
            )
            source_ids[source_spec.source_name] = str(source.id)
    return source_ids


async def import_project_file(project_file: Path, source_id: str) -> Counter[str]:
    source_dir = find_source_dir(project_file)
    if source_dir is None:
        raise ValueError(f"unable to locate source directory for {project_file}")
    source_spec = parse_source_dir(source_dir)
    stats = Counter(lines=0, imported=0)
    batch = []
    fallback_time = datetime.fromtimestamp(project_file.stat().st_mtime, tz=timezone.utc)

    with project_file.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            batch.append(
                build_log_ingest(
                    record,
                    source_id=source_id,
                    source=source_spec,
                    project_file=project_file,
                    line_number=line_number,
                    fallback_time=fallback_time,
                )
            )
            stats["lines"] += 1

            if len(batch) >= 100:
                async with AsyncSessionLocal() as session:
                    rows = await ingest(session, batch, evaluate_alerts=False)
                stats["imported"] += len(rows)
                batch = []

    if batch:
        async with AsyncSessionLocal() as session:
            rows = await ingest(session, batch, evaluate_alerts=False)
        stats["imported"] += len(rows)

    return stats


async def run_import(import_root: Path, *, clear_existing: bool) -> Counter[str]:
    if clear_existing:
        await clear_archive_state()

    source_ids = await ensure_sources(import_root)
    totals = Counter(sources=len(source_ids), files=0, lines=0, imported=0)

    for project_file in iter_project_files(import_root):
        source_dir = find_source_dir(project_file)
        if source_dir is None:
            raise ValueError(f"unable to locate source directory for {project_file}")
        source_name = source_dir.name
        file_stats = await import_project_file(project_file, source_ids[source_name])
        totals["files"] += 1
        totals["lines"] += file_stats["lines"]
        totals["imported"] += file_stats["imported"]

    return totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/import", help="Import root containing <IP>_<PORT> directories.")
    parser.add_argument("--clear-existing", action="store_true", help="Delete existing sources/logs before import.")
    args = parser.parse_args()

    totals = asyncio.run(run_import(Path(args.root), clear_existing=args.clear_existing))
    print(json.dumps(totals, sort_keys=True))


if __name__ == "__main__":
    main()
