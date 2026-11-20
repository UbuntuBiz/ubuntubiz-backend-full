import difflib
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.database.models import Product, ProductAlias


class ProductMatcher:
    """
    Tiered Product Matching Engine:
    1. Exact product name or exact alias match (Case-insensitive)
    2. Fuzzy / string distance token match (e.g. Albany vs albny)
    3. Confidence threshold (confidence >= 0.7 accepted, else ask owner)
    """

    CONFIDENCE_THRESHOLD = 0.70

    @classmethod
    def match_product(cls, db: Session, business_id: str, query_text: str) -> Dict[str, Any]:
        cleaned = query_text.strip().lower()

        # Step 1: Exact product name match
        prod = db.query(Product).filter(
            Product.business_id == business_id,
            Product.name.ilike(cleaned)
        ).first()
        if prod:
            return {
                "matched": True,
                "confidence": 1.0,
                "match_type": "exact_name",
                "product_id": prod.id,
                "product_name": prod.name,
                "sell_price": prod.sell_price,
                "unit": prod.unit
            }

        # Step 2: Exact alias match
        alias_entry = db.query(ProductAlias).filter(
            (ProductAlias.business_id == business_id) | (ProductAlias.business_id.is_(None)),
            ProductAlias.alias == cleaned
        ).first()
        if alias_entry and alias_entry.product:
            p = alias_entry.product
            return {
                "matched": True,
                "confidence": 0.95,
                "match_type": "exact_alias",
                "product_id": p.id,
                "product_name": p.name,
                "sell_price": p.sell_price,
                "unit": p.unit
            }

        # Step 3: Fuzzy similarity matching across all products & aliases in this shop
        products = db.query(Product).filter(Product.business_id == business_id).all()
        candidates = []
        for p in products:
            # Check full name
            score = difflib.SequenceMatcher(None, cleaned, p.name.lower()).ratio()
            candidates.append((score, p))
            # Check each individual word in product name (e.g. "albany" in "Albany Superior White Bread")
            for token in p.name.lower().split():
                token_score = difflib.SequenceMatcher(None, cleaned, token).ratio()
                candidates.append((token_score, p))
            # Check aliases
            for a in p.aliases:
                alias_score = difflib.SequenceMatcher(None, cleaned, a.alias.lower()).ratio()
                candidates.append((alias_score, p))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_prod = candidates[0]
            if best_score >= cls.CONFIDENCE_THRESHOLD:
                return {
                    "matched": True,
                    "confidence": round(best_score, 2),
                    "match_type": "fuzzy_match",
                    "product_id": best_prod.id,
                    "product_name": best_prod.name,
                    "sell_price": best_prod.sell_price,
                    "unit": best_prod.unit
                }

        return {
            "matched": False,
            "confidence": round(candidates[0][0], 2) if candidates else 0.0,
            "match_type": "low_confidence",
            "suggested_product": candidates[0][1].name if candidates else None,
            "message": f"Could not confidently match '{query_text}'. Please confirm with the shop owner."
        }
