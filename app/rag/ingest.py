"""RAG Knowledge Base Ingestion Script

This module provides a simple CLI to ingest knowledge chunks into the
`knowledge_chunks` table. It reads a directory of text files, generates
embeddings using the Gemini API, and stores the resulting records.

The script is intentionally lightweight – it does not perform any heavy
batch processing and can be extended later.
"""

import os
import pathlib
from typing import List

from fastapi import Depends

from app.config import settings
from app.database import get_session
from app.database.models.knowledge import KnowledgeChunk
from app.rag.retrieval import embed_text
from sqlalchemy.ext.asyncio import AsyncSession

async def ingest_directory(path: str, business_id: int, session: AsyncSession = Depends(get_session)) -> int:
    """Ingest all ``.txt`` files from *path* for a given business.

    Returns the number of chunks inserted.
    """
    base_path = pathlib.Path(path)
    if not base_path.is_dir():
        raise ValueError(f"{path!r} is not a directory")

    inserted = 0
    for file_path in base_path.rglob("*.txt"):
        text = file_path.read_text(encoding="utf-8")
        # Split large documents into smaller chunks (max 1000 chars)
        chunks = [text[i : i + 1000] for i in range(0, len(text), 1000)]
        for chunk in chunks:
            embedding = await embed_text(chunk)
            kc = KnowledgeChunk(
                business_id=business_id,
                scope="file",
                text=chunk,
                source=str(file_path),
                source_date=None,
                embedding=embedding,
            )
            session.add(kc)
            inserted += 1
    await session.commit()
    return inserted

# When run as a script ``python -m app.rag.ingest <dir> <biz_id>``
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Ingest knowledge files into the DB")
    parser.add_argument("directory", help="Path to the folder containing .txt files")
    parser.add_argument("business_id", type=int, help="Business identifier")
    args = parser.parse_args()

    async def main():
        async with get_session() as session:
            count = await ingest_directory(args.directory, args.business_id, session)
            print(f"Inserted {count} knowledge chunks")

    asyncio.run(main())
