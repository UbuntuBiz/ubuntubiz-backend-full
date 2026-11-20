"""Tenant-scoped service wrapper for knowledge retrieval."""

from typing import Any

from sqlalchemy.orm import Session

from app.rag.retrieval import KnowledgeRetriever


def rag_search(
    db: Session,
    query: str,
    business_id: str,
    top_k: int = 5
) -> list[dict[str, Any]]:
    return KnowledgeRetriever.search_knowledge(
        db=db,
        business_id=business_id,
        query=query,
        limit=top_k
    )
