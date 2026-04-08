import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

BASE = "/analytics/summary"
FULL = {"date_from": "2025-03-01", "date_to": "2025-03-10"}


def get(params: dict) -> tuple[int, dict | list]:
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


def test_invalid_group_by_returns_422():
    status, _ = get({**FULL, "group_by": "product"})
    assert status == 422


def test_invalid_marketplace_returns_422():
    status, _ = get({**FULL, "marketplace": "amazon"})
    assert status == 422


# ---------------------------------------------------------------------------
# Basic summary (no group_by)
# ---------------------------------------------------------------------------

def test_response_shape(seeded_db):
    status, body = get(FULL)
    assert status == 200
    assert isinstance(body, list) and len(body) == 1
    item = body[0]
    assert item["group"] == ""
    for field in ("group", "total_revenue", "total_cost", "gross_profit", "margin_percent",
                  "total_orders", "avg_order_value", "return_rate"):
        assert field in item


def test_full_range_summary(seeded_db):
    status, body = get(FULL)
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == pytest.approx(41540.00)
    assert item["total_cost"] == pytest.approx(12540.00)
    assert item["gross_profit"] == pytest.approx(29000.00)
    assert item["margin_percent"] == pytest.approx(69.81, abs=0.01)
    assert item["total_orders"] == 20
    assert item["avg_order_value"] == pytest.approx(2077.00)
    assert item["return_rate"] == pytest.approx(16.67, abs=0.01)


def test_no_data_returns_zeros(seeded_db):
    status, body = get({"date_from": "2020-01-01", "date_to": "2020-12-31"})
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == 0.0
    assert item["total_cost"] == 0.0
    assert item["gross_profit"] == 0.0
    assert item["total_orders"] == 0
    assert item["avg_order_value"] == 0.0
    assert item["return_rate"] == 0.0


# ---------------------------------------------------------------------------
# Marketplace filter
# ---------------------------------------------------------------------------

def test_filter_marketplace_ozon(seeded_db):
    status, body = get({**FULL, "marketplace": "ozon"})
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == pytest.approx(16750.00)
    assert item["total_cost"] == pytest.approx(5340.00)
    assert item["gross_profit"] == pytest.approx(11410.00)
    assert item["margin_percent"] == pytest.approx(68.12, abs=0.01)
    assert item["total_orders"] == 9
    assert item["avg_order_value"] == pytest.approx(1861.11, abs=0.01)
    assert item["return_rate"] == pytest.approx(14.29, abs=0.01)


def test_filter_marketplace_wildberries(seeded_db):
    status, body = get({**FULL, "marketplace": "wildberries"})
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == pytest.approx(15350.00)
    assert item["total_cost"] == pytest.approx(4600.00)
    assert item["gross_profit"] == pytest.approx(10750.00)
    assert item["margin_percent"] == pytest.approx(70.03, abs=0.01)
    assert item["total_orders"] == 7
    assert item["avg_order_value"] == pytest.approx(2192.86, abs=0.01)
    assert item["return_rate"] == pytest.approx(14.29, abs=0.01)


def test_filter_marketplace_yandex_market(seeded_db):
    status, body = get({**FULL, "marketplace": "yandex_market"})
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == pytest.approx(9440.00)
    assert item["total_cost"] == pytest.approx(2600.00)
    assert item["gross_profit"] == pytest.approx(6840.00)
    assert item["margin_percent"] == pytest.approx(72.46, abs=0.01)
    assert item["total_orders"] == 4
    assert item["avg_order_value"] == pytest.approx(2360.00)
    assert item["return_rate"] == pytest.approx(25.00, abs=0.01)


# ---------------------------------------------------------------------------
# Date range filtering
# ---------------------------------------------------------------------------

def test_date_range_partial(seeded_db):
    status, body = get({"date_from": "2025-03-01", "date_to": "2025-03-05"})
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == pytest.approx(21790.00)
    assert item["total_cost"] == pytest.approx(6760.00)
    assert item["gross_profit"] == pytest.approx(15030.00)
    assert item["margin_percent"] == pytest.approx(68.98, abs=0.01)
    assert item["total_orders"] == 10
    assert item["avg_order_value"] == pytest.approx(2179.00)
    assert item["return_rate"] == pytest.approx(11.11, abs=0.01)


def test_single_day(seeded_db):
    status, body = get({"date_from": "2025-03-01", "date_to": "2025-03-01"})
    assert status == 200
    item = body[0]
    # ORD-001: delivered 3*450=1350, ORD-002: delivered 1*1200=1200
    assert item["total_revenue"] == pytest.approx(2550.00)
    assert item["total_orders"] == 2
    assert item["return_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# group_by=marketplace
# ---------------------------------------------------------------------------

def test_group_by_marketplace_returns_list(seeded_db):
    status, body = get({**FULL, "group_by": "marketplace"})
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 3


def test_group_by_marketplace_shape(seeded_db):
    _, body = get({**FULL, "group_by": "marketplace"})
    item = body[0]
    for field in ("group", "total_revenue", "total_cost", "gross_profit",
                  "margin_percent", "total_orders", "avg_order_value", "return_rate"):
        assert field in item


def test_group_by_marketplace_values(seeded_db):
    _, body = get({**FULL, "group_by": "marketplace"})
    groups = {item["group"]: item for item in body}
    assert set(groups.keys()) == {"ozon", "wildberries", "yandex_market"}

    ozon = groups["ozon"]
    assert ozon["total_revenue"] == pytest.approx(16750.00)
    assert ozon["total_orders"] == 9
    assert ozon["return_rate"] == pytest.approx(14.29, abs=0.01)

    wb = groups["wildberries"]
    assert wb["total_revenue"] == pytest.approx(15350.00)
    assert wb["total_orders"] == 7

    ym = groups["yandex_market"]
    assert ym["total_revenue"] == pytest.approx(9440.00)
    assert ym["total_orders"] == 4
    assert ym["return_rate"] == pytest.approx(25.00, abs=0.01)


def test_group_by_marketplace_revenues_sum_to_total(seeded_db):
    _, body = get({**FULL, "group_by": "marketplace"})
    total = sum(item["total_revenue"] for item in body)
    assert total == pytest.approx(41540.00)


def test_group_by_marketplace_with_marketplace_filter(seeded_db):
    status, body = get({**FULL, "group_by": "marketplace", "marketplace": "ozon"})
    assert status == 200
    assert len(body) == 1
    assert body[0]["group"] == "ozon"
    assert body[0]["total_revenue"] == pytest.approx(16750.00)


# ---------------------------------------------------------------------------
# group_by=date
# ---------------------------------------------------------------------------

def test_group_by_date_returns_10_days(seeded_db):
    status, body = get({**FULL, "group_by": "date"})
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 10


def test_group_by_date_values(seeded_db):
    _, body = get({**FULL, "group_by": "date"})
    groups = {item["group"]: item for item in body}
    # 2025-03-01: ORD-001 delivered 1350, ORD-002 delivered 1200
    assert groups["2025-03-01"]["total_revenue"] == pytest.approx(2550.00)
    assert groups["2025-03-01"]["total_orders"] == 2
    # 2025-03-07: ORD-013 delivered 2600, ORD-014 delivered 3800
    assert groups["2025-03-07"]["total_revenue"] == pytest.approx(6400.00)


def test_group_by_date_narrow_range(seeded_db):
    status, body = get({"date_from": "2025-03-07", "date_to": "2025-03-07", "group_by": "date"})
    assert status == 200
    assert len(body) == 1
    assert body[0]["group"] == "2025-03-07"
    assert body[0]["total_revenue"] == pytest.approx(6400.00)
    assert body[0]["total_orders"] == 2


def test_group_by_date_no_data_returns_zeros(seeded_db):
    status, body = get({"date_from": "2020-01-01", "date_to": "2020-12-31", "group_by": "date"})
    assert status == 200
    assert len(body) == 1
    item = body[0]
    assert item["group"] == ""
    assert item["total_revenue"] == 0.0
    assert item["total_orders"] == 0


# ---------------------------------------------------------------------------
# group_by=status
# ---------------------------------------------------------------------------

def test_group_by_status_returns_three_groups(seeded_db):
    status, body = get({**FULL, "group_by": "status"})
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 3


def test_group_by_status_values(seeded_db):
    _, body = get({**FULL, "group_by": "status"})
    groups = {item["group"]: item for item in body}
    assert set(groups.keys()) == {"delivered", "returned", "cancelled"}

    delivered = groups["delivered"]
    assert delivered["total_revenue"] == pytest.approx(41540.00)
    assert delivered["total_cost"] == pytest.approx(12540.00)
    assert delivered["total_orders"] == 15
    assert delivered["avg_order_value"] == pytest.approx(2769.33, abs=0.01)
    assert delivered["return_rate"] == pytest.approx(0.0)

    returned = groups["returned"]
    assert returned["total_revenue"] == pytest.approx(0.0)
    assert returned["total_orders"] == 3
    assert returned["return_rate"] == pytest.approx(100.0)

    cancelled = groups["cancelled"]
    assert cancelled["total_revenue"] == pytest.approx(0.0)
    assert cancelled["total_orders"] == 2
    assert cancelled["return_rate"] == pytest.approx(0.0)
