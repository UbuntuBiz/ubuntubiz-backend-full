from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database.models import KnowledgeChunk
from app.core.logging import logger

PROHIBITED_RAG_KEYWORDS = ["current stock", "live balance", "sales total", "private password"]


class KnowledgeRetriever:
    @classmethod
    def search_knowledge(
        cls,
        db: Session,
        business_id: str,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        cleaned_query = query.strip().lower()

        # Guardrail: check for prohibited live operational queries
        for kw in PROHIBITED_RAG_KEYWORDS:
            if kw in cleaned_query:
                return [{
                    "text": "Live financial metrics and stock levels cannot be fetched from RAG. Please use authorised MCP tools (get_stock, get_metric).",
                    "source": "Security Policy Enforcement",
                    "source_date": "2026-01-01"
                }]

        # Query knowledge chunks scoped to global or this tenant only
        chunks = db.query(KnowledgeChunk).filter(
            (KnowledgeChunk.scope == "global") | (KnowledgeChunk.business_id == business_id),
            KnowledgeChunk.text.ilike(f"%{cleaned_query}%")
        ).limit(limit).all()

        return [
            {
                "text": c.text,
                "source": c.source,
                "source_date": c.source_date
            }
            for c in chunks
        ]
