"""Ingest text files into the tenant-scoped knowledge store."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import KnowledgeChunk
from app.core.tenant import set_session_tenant


def ingest_directory(path: str, business_id: str, session: Session) -> int:
    base_path = Path(path)
    if not base_path.is_dir():
        raise ValueError(f"{path!r} is not a directory")

    set_session_tenant(session, business_id)
    inserted = 0
    try:
        for file_path in sorted(base_path.rglob("*.txt")):
            text = file_path.read_text(encoding="utf-8")
            source = file_path.relative_to(base_path).as_posix()
            if not text.strip():
                session.query(KnowledgeChunk).filter(
                    KnowledgeChunk.business_id == business_id,
                    KnowledgeChunk.scope == "business_private",
                    KnowledgeChunk.source == source
                ).delete(synchronize_session=False)
                continue

            source_date = datetime.fromtimestamp(
                file_path.stat().st_mtime,
                timezone.utc
            ).date().isoformat()
            chunks = [text[index:index + 1000] for index in range(0, len(text), 1000)]

            for chunk_index, chunk in enumerate(chunks):
                existing = session.query(KnowledgeChunk).filter(
                    KnowledgeChunk.business_id == business_id,
                    KnowledgeChunk.scope == "business_private",
                    KnowledgeChunk.source == source,
                    KnowledgeChunk.chunk_index == chunk_index
                ).first()
                if existing and existing.text == chunk:
                    continue
                if existing:
                    existing.text = chunk
                    existing.source_date = source_date
                    existing.embedding = None
                    continue

                session.add(KnowledgeChunk(
                    business_id=business_id,
                    scope="business_private",
                    text=chunk,
                    source=source,
                    source_date=source_date,
                    chunk_index=chunk_index
                ))
                inserted += 1

            session.query(KnowledgeChunk).filter(
                KnowledgeChunk.business_id == business_id,
                KnowledgeChunk.scope == "business_private",
                KnowledgeChunk.source == source,
                KnowledgeChunk.chunk_index >= len(chunks)
            ).delete(synchronize_session=False)

        session.commit()
    except Exception:
        session.rollback()
        raise

    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest text files into the knowledge store")
    parser.add_argument("directory", help="Directory containing .txt files")
    parser.add_argument("business_id", help="Business UUID that owns the ingested content")
    args = parser.parse_args()

    with SessionLocal() as session:
        count = ingest_directory(args.directory, args.business_id, session)
    print(f"Inserted {count} knowledge chunks")


if __name__ == "__main__":
    main()
