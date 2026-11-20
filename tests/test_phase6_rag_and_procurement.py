import pytest
from app.rag.product_matching import ProductMatcher
from app.rag.retrieval import KnowledgeRetriever
from app.database.models import KnowledgeChunk, Bid, Supplier
from tests.test_phase2_inventory_and_sales import register_spaza_shop


def test_product_matcher_pipeline(client):
    token, biz_id = register_spaza_shop(client, "Nandi Spaza", "+27821000014")
    headers = {"Authorization": f"Bearer {token}"}

    # Add Albany Bread
    r_prod = client.post("/api/products", json={
        "name": "Albany Superior Sliced White Bread",
        "unit": "loaf",
        "sell_price": 1750,
        "aliases": ["albany", "bread", "isinkwa", "roti"],
        "initial_stock": 10
    }, headers=headers)
    assert r_prod.status_code == 201

    # 1. Exact alias match
    r_exact = client.post("/api/ai/chat", json={"message": "I sold 1 isinkwa"}, headers=headers)
    assert r_exact.status_code == 200
    assert r_exact.json()["data"]["status"] == "awaiting_owner_approval"
    assert r_exact.json()["data"]["items"][0]["product_name"] == "Albany Superior Sliced White Bread"

    # 2. Fuzzy match with slight typo
    r_fuzzy = client.post("/api/ai/chat", json={"message": "I sold 2 albnay"}, headers=headers)
    assert r_fuzzy.status_code == 200
    assert r_fuzzy.json()["data"]["status"] == "awaiting_owner_approval"

    # 3. Unrecognized item returns clarification
    r_unknown = client.post("/api/ai/chat", json={"message": "I sold 5 mysteriousitemxyz"}, headers=headers)
    assert r_unknown.status_code == 200
    assert r_unknown.json()["data"]["status"] == "clarification_needed"


def test_knowledge_retriever_and_prohibited_rag_queries(client):
    token, biz_id = register_spaza_shop(client, "Simphiwe Retail", "+27821000015")

    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        # Seed compliance knowledge
        chunk = KnowledgeChunk(
            scope="global",
            text="Spaza shops must adhere to local municipal health bylaws, maintain pest-free storage, and display prices in ZAR.",
            source="Department of Small Business Development - Spaza Policy Guidelines",
            source_date="2025-06-15"
        )
        db.add(chunk)
        db.commit()

        # Query compliance
        res = KnowledgeRetriever.search_knowledge(db, biz_id, "municipal health bylaws")
        assert len(res) >= 1
        assert "pest-free storage" in res[0]["text"]
        assert res[0]["source"] is not None
        assert res[0]["source_date"] == "2025-06-15"

        # Query live balance - must be refused by RAG guardrails
        res_prohibited = KnowledgeRetriever.search_knowledge(db, biz_id, "what is our current stock")
        assert "cannot be fetched from RAG" in res_prohibited[0]["text"]
    finally:
        db.close()


def test_group_purchasing_collaborative_workflow(client):
    # Shop 1 (Initiator)
    token1, biz1_id = register_spaza_shop(client, "Shop 1 - Soweto", "+27821000016")
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Shop 2 (Contributor)
    token2, biz2_id = register_spaza_shop(client, "Shop 2 - Meadowlands", "+27821000017")
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 1. Shop 1 creates Group Buying round for 100 bags of Iwisa Maize Meal
    r_round = client.post("/api/pools", json={
        "item_name": "Iwisa Maize Meal 10kg",
        "target_quantity": 100,
        "target_cents": 1200000,  # R12,000.00
        "duration_days": 7
    }, headers=headers1)
    assert r_round.status_code == 201
    round_data = r_round.json()
    round_id = round_data["id"]
    assert round_data["item_name"] == "Iwisa Maize Meal 10kg"
    assert round_data["status"] == "open"
    assert round_data["target_quantity"] == 100
    assert round_data["current_quantity"] == 0

    # 2. Shop 2 pledges 30 bags (R3,600.00)
    r_pledge = client.post(f"/api/pools/{round_id}/pledges", json={
        "quantity": 30,
        "amount_cents": 360000
    }, headers=headers2)
    assert r_pledge.status_code == 201
    assert r_pledge.json()["quantity"] == 30

    # 3. Verify round updated to 30% progress
    r_get = client.get(f"/api/pools/{round_id}", headers=headers1)
    assert r_get.status_code == 200
    updated_round = r_get.json()
    assert updated_round["current_quantity"] == 30
    assert updated_round["progress_percent"] == 30.0

    # 4. Register Supplier & Submit Bid
    r_sup = client.post("/api/pools/suppliers", json={
        "name": "Metro Cash & Carry Wholesalers",
        "contact_phone": "+27119001000",
        "area": "Crown Mines, Johannesburg",
        "catalog_summary": "Bulk grains, sugar, cooking oil, canned goods",
        "is_verified": True
    }, headers=headers1)
    assert r_sup.status_code == 201
    supplier_id = r_sup.json()["id"]

    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        bid = Bid(
            round_id=round_id,
            supplier_id=supplier_id,
            unit_price_cents=11000,  # R110.00 / bag (discounted)
            delivery_terms="Free delivery to Soweto spaza hub within 48h",
            status="submitted"
        )
        db.add(bid)
        db.commit()
    finally:
        db.close()

    # 5. Check bid status & comparison
    r_status = client.get(f"/api/pools/{round_id}/status", headers=headers1)
    assert r_status.status_code == 200
    comp = r_status.json()
    assert comp["best_bid"]["unit_price_zar"] == 110.00
    assert "Metro Cash & Carry" in comp["recommendation"]
