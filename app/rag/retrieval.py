from typing import List, Dict, Any, Optional
import re
from sqlalchemy import or_
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
        if not cleaned_query or limit <= 0:
            return []

        # Guardrail: check for prohibited live operational queries
        for kw in PROHIBITED_RAG_KEYWORDS:
            if kw in cleaned_query:
                return [{
                    "text": "Live financial metrics and stock levels cannot be fetched from RAG. Please use authorised MCP tools (get_stock, get_metric).",
                    "source": "Security Policy Enforcement",
                    "source_date": "2026-01-01"
                }]

        # Query knowledge chunks scoped to global or this tenant only
        terms = list(dict.fromkeys(re.findall(r"\w+", cleaned_query)))[:20]
        if not terms:
            return []

        chunks = db.query(KnowledgeChunk).filter(
            (KnowledgeChunk.scope == "global") | (KnowledgeChunk.business_id == business_id),
            or_(*(KnowledgeChunk.text.ilike(f"%{term}%") for term in terms))
        ).limit(max(limit * 10, limit)).all()

        ranked = []
        for chunk in chunks:
            matched_terms = sum(
                1 for term in terms if term in chunk.text.lower()
            )
            if not matched_terms:
                continue
            ranked.append((matched_terms / len(terms), chunk))

        ranked.sort(key=lambda result: result[0], reverse=True)
        return [
            {
                "text": c.text,
                "source": c.source,
                "source_date": c.source_date,
                "score": score
            }
            for score, c in ranked[:limit]
        ]
