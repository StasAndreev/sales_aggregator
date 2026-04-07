import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def get(params: dict = {}) -> tuple[int, dict]:
    r = client.get("/sales", params=params)
    body = r.json()
    print(f"\nStatus: {r.status_code}  Body: {body}")
    return r.status_code, body


# ---------------------------------------------------------------------------
# No filters
# ---------------------------------------------------------------------------

def test_no_filters_returns_all(seeded_db):
    status, body = get()
    assert status == 200
    assert body["total"] == 20
    assert len(body["items"]) == 20


def test_response_shape(seeded_db):
    status, body = get({"page_size": 1})
    assert status == 200
    item = body["items"][0]
    for field in ("order_id", "marketplace", "product_name", "quantity", "price", "cost_price", "status", "sold_at"):
        assert field in item


# ---------------------------------------------------------------------------
# Marketplace filter
# ---------------------------------------------------------------------------

def test_filter_marketplace_ozon(seeded_db):
    _, body = get({"marketplace": "ozon"})
    assert body["total"] == 9
    assert all(item["marketplace"] == "ozon" for item in body["items"])


def test_filter_marketplace_wildberries(seeded_db):
    _, body = get({"marketplace": "wildberries"})
    assert body["total"] == 7
    assert all(item["marketplace"] == "wildberries" for item in body["items"])


def test_filter_marketplace_yandex_market(seeded_db):
    _, body = get({"marketplace": "yandex_market"})
    assert body["total"] == 4
    assert all(item["marketplace"] == "yandex_market" for item in body["items"])


def test_invalid_marketplace_returns_422(seeded_db):
    status, _ = get({"marketplace": "amazon"})
    assert status == 422


# ---------------------------------------------------------------------------
# Status filter
# ---------------------------------------------------------------------------

def test_filter_status_delivered(seeded_db):
    _, body = get({"status": "delivered"})
    assert body["total"] == 15
    assert all(item["status"] == "delivered" for item in body["items"])


def test_filter_status_returned(seeded_db):
    _, body = get({"status": "returned"})
    assert body["total"] == 3
    assert all(item["status"] == "returned" for item in body["items"])


def test_filter_status_cancelled(seeded_db):
    _, body = get({"status": "cancelled"})
    assert body["total"] == 2
    assert all(item["status"] == "cancelled" for item in body["items"])


def test_invalid_status_returns_422(seeded_db):
    status, _ = get({"status": "pending"})
    assert status == 422


# ---------------------------------------------------------------------------
# Date filters
# ---------------------------------------------------------------------------

def test_filter_date_from(seeded_db):
    _, body = get({"date_from": "2025-03-08"})
    assert body["total"] == 6
    assert all(item["sold_at"] >= "2025-03-08" for item in body["items"])


def test_filter_date_to(seeded_db):
    _, body = get({"date_to": "2025-03-02"})
    assert body["total"] == 4
    assert all(item["sold_at"] <= "2025-03-02" for item in body["items"])


def test_filter_date_range(seeded_db):
    _, body = get({"date_from": "2025-03-03", "date_to": "2025-03-05"})
    assert body["total"] == 6
    assert all("2025-03-03" <= item["sold_at"] <= "2025-03-05" for item in body["items"])


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------

def test_filter_marketplace_and_status(seeded_db):
    _, body = get({"marketplace": "ozon", "status": "delivered"})
    assert body["total"] == 6
    assert all(item["marketplace"] == "ozon" and item["status"] == "delivered" for item in body["items"])


def test_filter_no_matches(seeded_db):
    _, body = get({"marketplace": "yandex_market", "status": "cancelled"})
    assert body["total"] == 0
    assert body["items"] == []


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_pagination_page_size(seeded_db):
    _, body = get({"page_size": 4})
    assert body["total"] == 20
    assert len(body["items"]) == 4


def test_pagination_all_pages_unique(seeded_db):
    page_size = 5
    all_ids = set()
    for page in range(1, 5):
        _, body = get({"page": page, "page_size": page_size})
        all_ids.update(item["order_id"] for item in body["items"])
    assert len(all_ids) == 20


def test_pagination_last_page(seeded_db):
    _, body = get({"page": 4, "page_size": 5})
    assert len(body["items"]) == 5
    assert body["total"] == 20


def test_pagination_beyond_last_page(seeded_db):
    _, body = get({"page": 99, "page_size": 20})
    assert body["total"] == 20
    assert body["items"] == []


def test_default_page_size(seeded_db):
    _, body = get()
    assert len(body["items"]) == 20


def test_invalid_page_returns_422(seeded_db):
    status, _ = get({"page": 0})
    assert status == 422


def test_invalid_page_size_returns_422(seeded_db):
    status, _ = get({"page_size": 0})
    assert status == 422
