from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def get(params: dict = {}) -> tuple[int, dict]:
    r = client.get("/sales", params=params)
    body = r.json()
    print(f"\nStatus: {r.status_code}  Body: {body}")
    return r.status_code, body

VALID_SALE = {
    "order_id": "ORD-001",
    "marketplace": "ozon",
    "product_name": "Кабель USB-C",
    "quantity": 3,
    "price": 450.00,
    "cost_price": 120.00,
    "status": "delivered",
    "sold_at": "2025-03-15",
}


def post(payload: list[dict]) -> tuple[int, dict]:
    r = client.post("/sales", json=payload)
    body = r.json()
    print(f"\nStatus: {r.status_code}  Body: {body}")
    return r.status_code, body


def failed_fields(body: dict) -> list[str]:
    return [err["field"] for item in body["failed"] for err in item["errors"]]


def test_empty():
    status, body = post([])
    assert status == 422


def test_all_valid():
    status, body = post([VALID_SALE])
    assert status == 200
    assert body["added"] == 1
    assert body["failed"] == []


def test_wrong_marketplace():
    sale = {**VALID_SALE, "marketplace": "amazon"}
    status, body = post([sale])
    assert status == 200
    assert body["added"] == 0
    assert any("marketplace" in f for f in failed_fields(body))


def test_wrong_status():
    sale = {**VALID_SALE, "status": "pending"}
    status, body = post([sale])
    assert status == 200
    assert body["added"] == 0
    assert any("status" in f for f in failed_fields(body))


def test_wrong_price_negative():
    sale = {**VALID_SALE, "price": -1.0}
    status, body = post([sale])
    assert status == 200
    assert body["added"] == 0
    assert any("price" in f for f in failed_fields(body))


def test_wrong_cost_price_negative():
    sale = {**VALID_SALE, "cost_price": -5.0}
    status, body = post([sale])
    assert status == 200
    assert body["added"] == 0
    assert any("cost_price" in f for f in failed_fields(body))


def test_wrong_quantity_zero():
    sale = {**VALID_SALE, "quantity": 0}
    status, body = post([sale])
    assert status == 200
    assert body["added"] == 0
    assert any("quantity" in f for f in failed_fields(body))


def test_wrong_sold_at_future():
    sale = {**VALID_SALE, "sold_at": "2099-01-01"}
    status, body = post([sale])
    assert status == 200
    assert body["added"] == 0
    assert any("sold_at" in f for f in failed_fields(body))


def test_wrong_field_name():
    sale = {**VALID_SALE, "prise": 450.00}
    del sale["price"]
    status, body = post([sale])
    assert status == 200
    assert body["added"] == 0
    assert any("price" in f for f in failed_fields(body))

def test_wrong_marketplace_and_sold_at_future():
    sale = {**VALID_SALE, "marketplace": "amazon", "sold_at": "2099-01-01"}
    status, body = post([VALID_SALE, sale])
    assert status == 200
    assert body["added"] == 1
    assert len(body["failed"]) == 1
    fields = failed_fields(body)
    assert any("marketplace" in f for f in fields)
    assert any("sold_at" in f for f in fields)


def test_batch_one_valid_one_invalid():
    invalid_sale = {**VALID_SALE, "marketplace": "amazon"}
    status, body = post([VALID_SALE, invalid_sale])
    assert status == 200
    assert body["added"] == 1
    assert len(body["failed"]) == 1
    assert body["failed"][0]["index"] == 1
    assert any("marketplace" in f for f in failed_fields(body))

def test_duplicate():
    status, body = post([VALID_SALE, VALID_SALE])
    assert status == 200
    assert body["added"] == 1
    assert body["failed"] == []


def test_post_then_get():
    status, body = post([VALID_SALE])
    status, body = get()
    assert status == 200
    assert body["items"][0] == VALID_SALE