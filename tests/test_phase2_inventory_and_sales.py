def register_spaza_shop(client, name: str, phone: str):
    r = client.post("/api/auth/register", json={
        "business_name": name,
        "area": "Soweto",
        "phone": phone,
        "password": "Password123!",
        "pin": "1234",
        "language": "en"
    })
    assert r.status_code == 201
    return r.json()["access_token"], r.json()["business_id"]


def test_product_creation_and_stock_initialization(client):
    token, biz_id = register_spaza_shop(client, "Sipho Spaza", "+27821000001")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Albany Bread with aliases and 20 initial stock
    prod_payload = {
        "name": "Albany Superior White Bread 700g",
        "unit": "loaf",
        "cost_price": 1400,  # R14.00
        "sell_price": 1750,  # R17.50
        "reorder_point": 5,
        "expiry_tracked": True,
        "aliases": ["bread", "albany", "roti", "isinkwa"],
        "initial_stock": 20
    }
    r = client.post("/api/products", json=prod_payload, headers=headers)
    assert r.status_code == 201
    prod = r.json()
    assert prod["name"] == "Albany Superior White Bread 700g"
    assert prod["qty_on_hand"] == 20
    assert "isinkwa" in prod["aliases"]
    prod_id = prod["id"]

    # Verify inventory endpoint confirms 20 loaves on hand
    r_inv = client.get(f"/api/inventory?product_id={prod_id}", headers=headers)
    assert r_inv.status_code == 200
    inv = r_inv.json()
    assert len(inv) == 1
    assert inv[0]["qty_on_hand"] == 20
    assert inv[0]["is_low_stock"] is False


def test_record_sale_reduces_stock_atomically(client):
    token, biz_id = register_spaza_shop(client, "Themba Corner", "+27821000002")
    headers = {"Authorization": f"Bearer {token}"}

    # Create Coca-Cola with 10 cans
    r_prod = client.post("/api/products", json={
        "name": "Coca-Cola 330ml Can",
        "unit": "can",
        "cost_price": 1000,
        "sell_price": 1500,  # R15.00
        "reorder_point": 3,
        "initial_stock": 10
    }, headers=headers)
    prod_id = r_prod.json()["id"]

    # Record sale of 2 cans
    sale_payload = {
        "items": [{"product_id": prod_id, "qty": 2}],
        "payment_type": "cash",
        "idempotency_key": "sale_test_001"
    }
    r_sale = client.post("/api/sales", json=sale_payload, headers=headers)
    assert r_sale.status_code == 201
    sale_data = r_sale.json()
    assert sale_data["total"] == 3000  # 2 * 1500 cents = R30.00
    assert sale_data["total_zar"] == 30.00
    assert sale_data["payment_type"] == "cash"

    # Verify stock dropped to 8
    r_inv = client.get(f"/api/inventory?product_id={prod_id}", headers=headers)
    assert r_inv.status_code == 200
    assert r_inv.json()[0]["qty_on_hand"] == 8

    # Verify event ledger entry
    r_events = client.get(f"/api/inventory/events?product_id={prod_id}", headers=headers)
    assert r_events.status_code == 200
    events = r_events.json()
    # Most recent event should be sale with delta -2
    assert events[0]["type"] == "sale"
    assert events[0]["qty_delta"] == -2


def test_negative_stock_prevention(client):
    token, biz_id = register_spaza_shop(client, "Lindiwe Groceries", "+27821000003")
    headers = {"Authorization": f"Bearer {token}"}

    # Create product with 2 in stock
    r_prod = client.post("/api/products", json={
        "name": "Lucky Star Pilchards 400g",
        "unit": "tin",
        "sell_price": 2500,
        "initial_stock": 2
    }, headers=headers)
    prod_id = r_prod.json()["id"]

    # Attempt to sell 5 items (exceeding stock of 2)
    sale_payload = {
        "items": [{"product_id": prod_id, "qty": 5}],
        "payment_type": "cash",
        "idempotency_key": "sale_excess_stock_test"
    }
    r_sale = client.post("/api/sales", json=sale_payload, headers=headers)
    assert r_sale.status_code == 400
    assert "Insufficient stock" in r_sale.json()["detail"]

    # Verify stock remains unchanged at 2
    r_inv = client.get(f"/api/inventory?product_id={prod_id}", headers=headers)
    assert r_inv.json()[0]["qty_on_hand"] == 2


def test_undo_inventory_event_restores_stock(client):
    token, biz_id = register_spaza_shop(client, "Musa Market", "+27821000004")
    headers = {"Authorization": f"Bearer {token}"}

    r_prod = client.post("/api/products", json={
        "name": "Sunfoil Cooking Oil 2L",
        "unit": "bottle",
        "sell_price": 8500,
        "initial_stock": 10
    }, headers=headers)
    prod_id = r_prod.json()["id"]

    # Mistakenly adjust stock by -4 due to damage
    r_adj = client.post("/api/inventory/events", json={
        "product_id": prod_id,
        "type": "adjustment",
        "qty_delta": -4,
        "reason": "Accidental damage logged by cashier",
        "idempotency_key": "erroneous_damage_log_1"
    }, headers=headers)
    assert r_adj.status_code == 201
    event_id = r_adj.json()["id"]

    # Verify stock dropped to 6
    r_inv1 = client.get(f"/api/inventory?product_id={prod_id}", headers=headers)
    assert r_inv1.json()[0]["qty_on_hand"] == 6

    # Undo event
    r_undo = client.post(f"/api/inventory/undo/{event_id}", headers=headers)
    assert r_undo.status_code == 200
    undo_data = r_undo.json()
    assert undo_data["type"] == "reversal"
    assert undo_data["qty_delta"] == 4  # Restores 4
    assert undo_data["reverses_event_id"] == event_id

    # Verify stock is restored to 10
    r_inv2 = client.get(f"/api/inventory?product_id={prod_id}", headers=headers)
    assert r_inv2.json()[0]["qty_on_hand"] == 10

    # Cannot undo the same event twice
    r_undo_again = client.post(f"/api/inventory/undo/{event_id}", headers=headers)
    assert r_undo_again.status_code == 400


def test_low_stock_detection_and_expenses_summary(client):
    token, biz_id = register_spaza_shop(client, "Khanya Store", "+27821000005")
    headers = {"Authorization": f"Bearer {token}"}

    # Product with reorder_point 5, initial stock 4 (already low)
    client.post("/api/products", json={
        "name": "Iwisa Maize Meal 2.5kg",
        "unit": "bag",
        "sell_price": 3800,
        "reorder_point": 5,
        "initial_stock": 4
    }, headers=headers)

    # Check low stock endpoint
    r_low = client.get("/api/products/low-stock", headers=headers)
    assert r_low.status_code == 200
    low_items = r_low.json()
    assert len(low_items) == 1
    assert low_items[0]["product_name"] == "Iwisa Maize Meal 2.5kg"
    assert low_items[0]["is_low_stock"] is True

    # Record expense
    r_exp = client.post("/api/expenses", json={
        "category": "electricity",
        "amount": 25000,  # R250.00
        "receipt_ref": "Eskom-Prepaid-12345"
    }, headers=headers)
    assert r_exp.status_code == 201
    assert r_exp.json()["amount_zar"] == 250.00

    # Check summary
    r_sum = client.get("/api/sales/summary", headers=headers)
    assert r_sum.status_code == 200
    summary = r_sum.json()
    assert summary["total_expenses_cents"] == 25000
