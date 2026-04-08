from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import services.currency as currency_module
from main import app

client = TestClient(app)

BASE = "/analytics/summary-usd"
FULL = {"date_from": "2025-03-01", "date_to": "2025-03-10"}

MOCK_RATE = 100.0


def get(params: dict, mock_rate: float = MOCK_RATE) -> tuple[int, list]:
    with patch("routers.analytics.get_usd_rate", return_value=mock_rate):
        r = client.get(BASE, params=params)
    body = r.json()
    print(f"\nStatus: {r.status_code}  Body: {body}")
    return r.status_code, body


@pytest.fixture(autouse=True)
def reset_currency_cache():
    currency_module._cached_rate = None
    currency_module._cache_ts = 0.0
    yield


# ---------------------------------------------------------------------------
# Validation (same params as /summary)
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
# 503 when CBR API unavailable
# ---------------------------------------------------------------------------

def test_api_unavailable_returns_503(seeded_db):
    from services.currency import CurrencyUnavailableError
    with patch("routers.analytics.get_usd_rate", side_effect=CurrencyUnavailableError("CBR API недоступен")):
        r = client.get(BASE, params=FULL)
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# Money fields converted, non-money fields unchanged
# ---------------------------------------------------------------------------

def test_money_fields_divided_by_rate(seeded_db):
    # Known RUB values from test_analytics_get.py::test_full_range_summary
    status, body = get(FULL, mock_rate=100.0)
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == pytest.approx(415.40)
    assert item["total_cost"] == pytest.approx(125.40)
    assert item["gross_profit"] == pytest.approx(290.00)
    assert item["avg_order_value"] == pytest.approx(20.77)


def test_non_money_fields_unchanged(seeded_db):
    status, body = get(FULL, mock_rate=100.0)
    assert status == 200
    item = body[0]
    assert item["total_orders"] == 20
    assert item["margin_percent"] == pytest.approx(69.81, abs=0.01)
    assert item["return_rate"] == pytest.approx(16.67, abs=0.01)


def test_different_rate_scales_proportionally(seeded_db):
    _, body_100 = get(FULL, mock_rate=100.0)
    _, body_50 = get(FULL, mock_rate=50.0)
    # With half the rate, USD values should be doubled
    assert body_50[0]["total_revenue"] == pytest.approx(body_100[0]["total_revenue"] * 2)
    assert body_50[0]["total_cost"] == pytest.approx(body_100[0]["total_cost"] * 2)


def test_response_shape(seeded_db):
    status, body = get(FULL)
    assert status == 200
    assert isinstance(body, list) and len(body) == 1
    item = body[0]
    for field in ("group", "total_revenue", "total_cost", "gross_profit", "margin_percent",
                  "total_orders", "avg_order_value", "return_rate"):
        assert field in item


# ---------------------------------------------------------------------------
# Empty data
# ---------------------------------------------------------------------------

def test_no_data_returns_zeros(seeded_db):
    status, body = get({"date_from": "2020-01-01", "date_to": "2020-12-31"})
    assert status == 200
    item = body[0]
    assert item["total_revenue"] == 0.0
    assert item["total_cost"] == 0.0
    assert item["gross_profit"] == 0.0
    assert item["avg_order_value"] == 0.0
    assert item["total_orders"] == 0


# ---------------------------------------------------------------------------
# Filters and group_by pass through correctly
# ---------------------------------------------------------------------------

def test_marketplace_filter_applied(seeded_db):
    # ozon total_revenue in RUB = 16750, so at rate=100 → 167.50
    status, body = get({**FULL, "marketplace": "ozon"}, mock_rate=100.0)
    assert status == 200
    assert body[0]["total_revenue"] == pytest.approx(167.50)
    assert body[0]["total_orders"] == 9


def test_group_by_marketplace_converts_each_group(seeded_db):
    status, body = get({**FULL, "group_by": "marketplace"}, mock_rate=100.0)
    assert status == 200
    assert len(body) == 3
    groups = {item["group"]: item for item in body}
    # ozon RUB=16750 → USD=167.50
    assert groups["ozon"]["total_revenue"] == pytest.approx(167.50)
    # wildberries RUB=15350 → USD=153.50
    assert groups["wildberries"]["total_revenue"] == pytest.approx(153.50)
    # total_orders (non-money) unchanged
    assert groups["ozon"]["total_orders"] == 9
    assert groups["wildberries"]["total_orders"] == 7


def test_group_by_status_non_delivered_revenue_is_zero(seeded_db):
    status, body = get({**FULL, "group_by": "status"}, mock_rate=100.0)
    assert status == 200
    groups = {item["group"]: item for item in body}
    # Returned/cancelled have 0 revenue in RUB, 0/rate = 0 in USD too
    assert groups["returned"]["total_revenue"] == 0.0
    assert groups["cancelled"]["total_revenue"] == 0.0


# ---------------------------------------------------------------------------
# Cache unit tests (test services/currency.py directly)
# ---------------------------------------------------------------------------

CBR_RESPONSE = {
    "Valute": {
        "USD": {"Value": 90.0, "Nominal": 1}
    }
}


def test_get_usd_rate_fetches_from_api():
    mock_resp = MagicMock()
    mock_resp.json.return_value = CBR_RESPONSE
    with patch("httpx.get", return_value=mock_resp) as mock_get:
        rate = currency_module.get_usd_rate()
    assert rate == pytest.approx(90.0)
    mock_get.assert_called_once()


def test_rate_cached_within_ttl():
    mock_resp = MagicMock()
    mock_resp.json.return_value = CBR_RESPONSE
    with patch("httpx.get", return_value=mock_resp) as mock_get:
        currency_module.get_usd_rate()
        currency_module.get_usd_rate()
    # Second call should use cache — httpx.get called only once
    assert mock_get.call_count == 1


def test_cache_expires_after_ttl():
    mock_resp = MagicMock()
    mock_resp.json.return_value = CBR_RESPONSE
    with patch("httpx.get", return_value=mock_resp) as mock_get:
        # Double-checked locking calls time.monotonic() twice per cache miss
        with patch("time.monotonic", side_effect=[0.0, 0.0, 3601.0, 3601.0]):
            currency_module.get_usd_rate()  # fills cache at t=0
            currency_module.get_usd_rate()  # t=3601 > TTL, re-fetches
    assert mock_get.call_count == 2


def test_api_error_raises_currency_unavailable():
    with patch("httpx.get", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(currency_module.CurrencyUnavailableError):
            currency_module.get_usd_rate()


def test_api_error_does_not_pollute_cache():
    with patch("httpx.get", side_effect=httpx.ConnectError("timeout")):
        with pytest.raises(currency_module.CurrencyUnavailableError):
            currency_module.get_usd_rate()
    assert currency_module._cached_rate is None


def test_stale_rate_served_when_api_down():
    currency_module._cached_rate = 85.0
    currency_module._cache_ts = 0.0  # expired
    with patch("httpx.get", side_effect=httpx.ConnectError("timeout")):
        rate = currency_module.get_usd_rate()
    assert rate == pytest.approx(85.0)


def test_malformed_response_raises_currency_unavailable():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Valute": {}}  # USD key missing
    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(currency_module.CurrencyUnavailableError):
            currency_module.get_usd_rate()


def test_malformed_response_serves_stale():
    currency_module._cached_rate = 85.0
    currency_module._cache_ts = 0.0
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Valute": {}}
    with patch("httpx.get", return_value=mock_resp):
        rate = currency_module.get_usd_rate()
    assert rate == pytest.approx(85.0)


def test_nominal_not_1():
    # Some currencies have Nominal != 1; ensure we divide correctly
    response = {"Valute": {"USD": {"Value": 180.0, "Nominal": 2}}}
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    with patch("httpx.get", return_value=mock_resp):
        rate = currency_module.get_usd_rate()
    assert rate == pytest.approx(90.0)
