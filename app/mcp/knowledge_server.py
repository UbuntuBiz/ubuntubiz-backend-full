from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.rag.product_matching import ProductMatcher
from app.rag.retrieval import KnowledgeRetriever


class KnowledgeMCPServer:
    """
    Model Context Protocol (MCP) tool provider for Product Matching and Compliance/Rules Knowledge.
    """

    @classmethod
    def match_product(cls, db: Session, business_id: str, text: str) -> Dict[str, Any]:
        return ProductMatcher.match_product(db, business_id, text)

    @classmethod
    def search_knowledge(cls, db: Session, business_id: str, query: str) -> List[Dict[str, Any]]:
        return KnowledgeRetriever.search_knowledge(db, business_id, query)
