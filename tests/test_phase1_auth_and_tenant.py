def test_health_endpoints(client):
    r1 = client.get("/health")
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] == "healthy"
    assert data1["chain_id"] == 43113

    r2 = client.get("/api/health")
    assert r2.status_code == 200
    assert r2.json()["status"] == "healthy"


def test_spaza_registration_and_login(client):
    reg_payload = {
        "business_name": "Sipho Corner Spaza",
        "area": "Soweto - Orlando West",
        "phone": "+27821112222",
        "password": "StrongPassword123!",
        "pin": "1234",
        "language": "zu"
    }
    r = client.post("/api/auth/register", json=reg_payload)
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "owner"
    assert data["business_name"] == "Sipho Corner Spaza"

    # Test Duplicate Registration Prevention
    r_dup = client.post("/api/auth/register", json=reg_payload)
    assert r_dup.status_code == 400

    # Test Login with Password
    login_payload = {
        "phone": "+27821112222",
        "password": "StrongPassword123!"
    }
    r_login = client.post("/api/auth/login", json=login_payload)
    assert r_login.status_code == 200
    token_data = r_login.json()
    assert token_data["access_token"] is not None

    # Test Login with PIN
    pin_payload = {
        "phone": "+27821112222",
        "pin": "1234"
    }
    r_pin = client.post("/api/auth/login/pin", json=pin_payload)
    assert r_pin.status_code == 200

    # Test Invalid Password
    r_bad = client.post("/api/auth/login", json={"phone": "+27821112222", "password": "WrongPassword"})
    assert r_bad.status_code == 401


def test_tenant_isolation_shop_a_vs_shop_b(client):
    # Register Shop A
    r_a = client.post("/api/auth/register", json={
        "business_name": "Shop A - Mamelodi Retail",
        "area": "Mamelodi East",
        "phone": "+27823334444",
        "password": "PasswordShopA1!",
        "pin": "4321",
        "language": "en"
    })
    assert r_a.status_code == 201
    token_a = r_a.json()["access_token"]
    biz_a_id = r_a.json()["business_id"]

    # Register Shop B
    r_b = client.post("/api/auth/register", json={
        "business_name": "Shop B - Khayelitsha Fresh",
        "area": "Khayelitsha Site B",
        "phone": "+27825556666",
        "password": "PasswordShopB2!",
        "pin": "8765",
        "language": "xh"
    })
    assert r_b.status_code == 201
    token_b = r_b.json()["access_token"]
    biz_b_id = r_b.json()["business_id"]

    assert biz_a_id != biz_b_id

    # Shop A requests its business profile
    headers_a = {"Authorization": f"Bearer {token_a}"}
    r_get_a = client.get("/api/business", headers=headers_a)
    assert r_get_a.status_code == 200
    data_a = r_get_a.json()
    assert data_a["id"] == biz_a_id
    assert data_a["name"] == "Shop A - Mamelodi Retail"
    assert data_a["id"] != biz_b_id

    # Shop B requests its business profile
    headers_b = {"Authorization": f"Bearer {token_b}"}
    r_get_b = client.get("/api/business", headers=headers_b)
    assert r_get_b.status_code == 200
    data_b = r_get_b.json()
    assert data_b["id"] == biz_b_id
    assert data_b["name"] == "Shop B - Khayelitsha Fresh"

    # Verify Shop A me endpoint
    r_me = client.get("/api/auth/me", headers=headers_a)
    assert r_me.status_code == 200
    assert r_me.json()["business_id"] == biz_a_id
