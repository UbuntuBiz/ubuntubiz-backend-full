from datetime import date, datetime, timedelta, timezone
from tests.test_phase2_inventory_and_sales import register_spaza_shop


def test_daily_metrics_and_profit_computation(client):
    token, biz_id = register_spaza_shop(client, "Gogo Dlamini Spaza", "+27821000008")
    headers = {"Authorization": f"Bearer {token}"}

    # Create Product: Cost R10.00 (1000c), Sell R16.00 (1600c)
    r_prod = client.post("/api/products", json={
        "name": "Bakers Blue Label Marie Biscuits 200g",
        "unit": "pack",
        "cost_price": 1000,
        "sell_price": 1600,
        "reorder_point": 5,
        "initial_stock": 50
    }, headers=headers)
    prod_id = r_prod.json()["id"]

    # Sell 5 packs = Revenue R80.00 (8000c), Cost = R50.00 (5000c), Gross Profit = R30.00 (3000c)
    client.post("/api/sales", json={
        "items": [{"product_id": prod_id, "qty": 5}],
        "payment_type": "cash",
        "idempotency_key": "sale_analytics_1"
    }, headers=headers)

    # Log Expense: Transport R20.00 (2000c)
    client.post("/api/expenses", json={
        "category": "transport",
        "amount": 2000,
        "receipt_ref": "Taxi-To-Wholesaler"
    }, headers=headers)

    # Query Daily Metrics Endpoint
    today = str(datetime.now(timezone.utc).date())
    r_metrics = client.get(f"/api/analytics/daily?target_date={today}", headers=headers)
    assert r_metrics.status_code == 200
    metrics = {m["metric"]: m["value"] for m in r_metrics.json()}

    assert metrics["daily_sales"] == 8000.0  # R80.00
    assert metrics["gross_profit"] == 3000.0  # R30.00
    assert metrics["total_expenses"] == 2000.0  # R20.00
    assert metrics["cash_variance"] == 6000.0  # R80 cash - R20 exp = R60

    # Query Profit Summary Endpoint
    r_profit = client.get("/api/analytics/profit", headers=headers)
    assert r_profit.status_code == 200
    profit = r_profit.json()
    assert profit["total_sales_zar"] == 80.00
    assert profit["gross_profit_zar"] == 30.00
    assert profit["gross_margin_percent"] == 37.5  # (30/80)*100


def test_alert_detection_and_resolution(client):
    token, biz_id = register_spaza_shop(client, "Bongani Store", "+27821000009")
    headers = {"Authorization": f"Bearer {token}"}

    # Create Product with stock (2) <= reorder point (5) -> Triggers alert
    client.post("/api/products", json={
        "name": "Koo Baked Beans 410g",
        "unit": "tin",
        "cost_price": 1200,
        "sell_price": 1800,
        "reorder_point": 5,
        "initial_stock": 2
    }, headers=headers)

    # Fetch Alerts
    r_alerts = client.get("/api/analytics/alerts", headers=headers)
    assert r_alerts.status_code == 200
    alerts = r_alerts.json()
    assert len(alerts) >= 1
    alert = alerts[0]
    assert alert["type"] == "low_stock_risk"
    assert "Koo Baked Beans" in alert["message"]
    assert alert["status"] == "active"
    alert_id = alert["id"]

    # Resolve Alert
    r_resolve = client.post(f"/api/analytics/alerts/{alert_id}/resolve", headers=headers)
    assert r_resolve.status_code == 200
    assert r_resolve.json()["status"] == "resolved"


def test_stock_health_and_dead_stock_detection(client):
    token, biz_id = register_spaza_shop(client, "Vusi Corner", "+27821000010")
    headers = {"Authorization": f"Bearer {token}"}

    # Product with stock but 0 sales = dead_stock
    client.post("/api/products", json={
        "name": "Slow-Moving Canned Asparagus",
        "unit": "can",
        "sell_price": 4500,
        "reorder_point": 2,
        "initial_stock": 10
    }, headers=headers)

    # Product with 0 stock = stockout
    client.post("/api/products", json={
        "name": "Sold-Out Sugar 1kg",
        "unit": "pack",
        "sell_price": 2200,
        "reorder_point": 5,
        "initial_stock": 0
    }, headers=headers)

    r_health = client.get("/api/analytics/stock", headers=headers)
    assert r_health.status_code == 200
    health_items = {item["product_name"]: item["status"] for item in r_health.json()}

    assert health_items["Slow-Moving Canned Asparagus"] == "dead_stock"
    assert health_items["Sold-Out Sugar 1kg"] == "stockout"


def test_morning_business_brief(client):
    token, biz_id = register_spaza_shop(client, "Mandla Quick Spaza", "+27821000011")
    headers = {"Authorization": f"Bearer {token}"}

    r_brief = client.get("/api/analytics/morning-brief", headers=headers)
    assert r_brief.status_code == 200
    brief = r_brief.json()
    assert brief["business_name"] == "Mandla Quick Spaza"
    assert "narrative" in brief
    assert "Good morning Mandla Quick Spaza" in brief["narrative"]
