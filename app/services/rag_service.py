"""RAG service layer

Provides high‑level functions that the business service layer can call to
perform knowledge retrieval without exposing the lower‑level retrieval
implementation directly.
"""

from typing import List, Dict, Any

from app.rag.retrieval import search_knowledge

async def rag_search(query: str, business_id: int, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search the knowledge base for *query* scoped to *business_id*.

    Returns a list of result dictionaries containing ``text`` and ``source``
    fields. The function applies a simple filter to ensure results belong to the
    requested business.
    """
    raw_results = await search_knowledge(query, business_id=business_id, limit=top_k)
    # Assume ``search_knowledge`` returns a list of ``KnowledgeChunk`` objects
    # with ``text`` and ``source`` attributes.
    formatted = [
        {"text": r.text, "source": r.source, "score": getattr(r, "score", None)}
        for r in raw_results
    ]
    return formatted
