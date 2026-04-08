import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

BASE = "/analytics/top-products"
FULL = {"date_from": "2025-03-01", "date_to": "2025-03-10"}


def get(params: dict) -> tuple[int, list]:
    r = client.get(BASE, params=params)
    body = r.json()
    print(f"\nStatus: {r.status_code}  Body: {body}")
    return r.status_code, body


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_missing_date_from_returns_422():
    status, _ = get({"date_to": "2025-03-10"})
    assert status == 422


def test_missing_date_to_returns_422():
    status, _ = get({"date_from": "2025-03-01"})
    assert status == 422


def test_invalid_sort_by_returns_422():
    status, _ = get({**FULL, "sort_by": "name"})
    assert status == 422


def test_limit_zero_returns_422():
    status, _ = get({**FULL, "limit": 0})
    assert status == 422


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

def test_response_shape(seeded_db):
    status, body = get(FULL)
    assert status == 200
    assert isinstance(body, list)
    item = body[0]
    for field in ("product_name", "revenue", "quantity", "profit"):
        assert field in item


# ---------------------------------------------------------------------------
# Empty data
# ---------------------------------------------------------------------------

def test_no_data_returns_empty_list(seeded_db):
    status, body = get({"date_from": "2020-01-01", "date_to": "2020-12-31"})
    assert status == 200
    assert body == []


# ---------------------------------------------------------------------------
# sort_by=revenue (default)
# ---------------------------------------------------------------------------

def test_default_sort_is_revenue(seeded_db):
    _, body_default = get(FULL)
    _, body_revenue = get({**FULL, "sort_by": "revenue"})
    assert body_default == body_revenue


def test_sort_by_revenue_top1(seeded_db):
    _, body = get({**FULL, "sort_by": "revenue", "limit": 1})
    assert len(body) == 1
    assert body[0]["product_name"] == "Наушники TWS"
    assert body[0]["revenue"] == pytest.approx(10300.00)
    assert body[0]["quantity"] == 4
    assert body[0]["profit"] == pytest.approx(7100.00)


def test_sort_by_revenue_top3(seeded_db):
    _, body = get({**FULL, "sort_by": "revenue", "limit": 3})
    assert len(body) == 3
    names = [item["product_name"] for item in body]
    assert names[0] == "Наушники TWS"
    assert names[1] == "Кабель USB-C"
    assert names[2] == "Чехол для iPhone 15"
    assert body[1]["revenue"] == pytest.approx(9390.00)
    assert body[2]["revenue"] == pytest.approx(4500.00)


def test_sort_by_revenue_all_8(seeded_db):
    _, body = get({**FULL, "sort_by": "revenue", "limit": 10})
    assert len(body) == 8  # 8 unique products in dataset


def test_sort_by_revenue_descending(seeded_db):
    _, body = get({**FULL, "sort_by": "revenue"})
    revenues = [item["revenue"] for item in body]
    assert revenues == sorted(revenues, reverse=True)


# ---------------------------------------------------------------------------
# sort_by=quantity
# ---------------------------------------------------------------------------

def test_sort_by_quantity_top1(seeded_db):
    _, body = get({**FULL, "sort_by": "quantity", "limit": 1})
    assert len(body) == 1
    assert body[0]["product_name"] == "Кабель USB-C"
    assert body[0]["quantity"] == 22
    assert body[0]["revenue"] == pytest.approx(9390.00)


def test_sort_by_quantity_descending(seeded_db):
    _, body = get({**FULL, "sort_by": "quantity"})
    quantities = [item["quantity"] for item in body]
    assert quantities == sorted(quantities, reverse=True)


# ---------------------------------------------------------------------------
# sort_by=profit
# ---------------------------------------------------------------------------

def test_sort_by_profit_top1(seeded_db):
    _, body = get({**FULL, "sort_by": "profit", "limit": 1})
    assert len(body) == 1
    assert body[0]["product_name"] == "Наушники TWS"
    assert body[0]["profit"] == pytest.approx(7100.00)


def test_sort_by_profit_top3(seeded_db):
    _, body = get({**FULL, "sort_by": "profit", "limit": 3})
    names = [item["product_name"] for item in body]
    assert names[0] == "Наушники TWS"
    assert names[1] == "Кабель USB-C"
    assert names[2] == "Чехол для iPhone 15"
    assert body[0]["profit"] == pytest.approx(7100.00)
    assert body[1]["profit"] == pytest.approx(6750.00)
    assert body[2]["profit"] == pytest.approx(3100.00)


def test_sort_by_profit_descending(seeded_db):
    _, body = get({**FULL, "sort_by": "profit"})
    profits = [item["profit"] for item in body]
    assert profits == sorted(profits, reverse=True)


# ---------------------------------------------------------------------------
# limit
# ---------------------------------------------------------------------------

def test_limit_respected(seeded_db):
    _, body = get({**FULL, "limit": 3})
    assert len(body) == 3


def test_limit_larger_than_results(seeded_db):
    _, body = get({**FULL, "limit": 100})
    assert len(body) == 8  # only 8 unique products


def test_limit_1(seeded_db):
    _, body = get({**FULL, "limit": 1})
    assert len(body) == 1


# ---------------------------------------------------------------------------
# Returned/cancelled orders excluded from metrics
# ---------------------------------------------------------------------------

def test_returned_orders_not_counted_in_revenue(seeded_db):
    # ORD-019: Наушники TWS returned, qty=2, price=2500 → should NOT add to revenue
    # Delivered for Наушники TWS: ORD-003 (2*2500) + ORD-008 (1*2700) + ORD-013 (1*2600) = 10300
    _, body = get({**FULL, "sort_by": "revenue", "limit": 1})
    assert body[0]["product_name"] == "Наушники TWS"
    assert body[0]["revenue"] == pytest.approx(10300.00)
    assert body[0]["quantity"] == 4  # 2+1+1, not 6


def test_cancelled_orders_not_counted(seeded_db):
    # ORD-007: Коврик для мыши XL cancelled qty=2; ORD-016: Мышь беспроводная cancelled qty=1
    # Коврик revenue should only be ORD-018: 3*950 = 2850
    _, body = get({**FULL, "sort_by": "revenue", "limit": 10})
    products = {item["product_name"]: item for item in body}
    assert products["Коврик для мыши XL"]["revenue"] == pytest.approx(2850.00)
    assert products["Коврик для мыши XL"]["quantity"] == 3


# ---------------------------------------------------------------------------
# Date range filtering
# ---------------------------------------------------------------------------

def test_date_range_limits_products(seeded_db):
    # 2025-03-01 only: ORD-001 Кабель USB-C delivered, ORD-002 Чехол iPhone delivered
    _, body = get({"date_from": "2025-03-01", "date_to": "2025-03-01", "sort_by": "revenue"})
    assert len(body) == 2
    names = {item["product_name"] for item in body}
    assert names == {"Кабель USB-C", "Чехол для iPhone 15"}
