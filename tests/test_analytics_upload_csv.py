import io

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

BASE = "/sales/upload-csv"

HEADER = "order_id,marketplace,product_name,quantity,price,cost_price,status,sold_at\n"
VALID_ROW = "ORD-001,ozon,Кабель USB-C,3,450.00,120.00,delivered,2025-03-01\n"


def upload(csv_text: str) -> tuple[int, dict]:
    r = client.post(
        BASE,
        files={"file": ("data.csv", csv_text.encode(), "text/csv")},
    )
    body = r.json()
    print(f"\nStatus: {r.status_code}  Body: {body}")
    return r.status_code, body


def error_fields(body: dict) -> list[str]:
    return [err["field"] for item in body["errors"] for err in item["errors"]]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_sample_csv():
    with open("sample_data.csv", "rb") as f:
        r = client.post(BASE, files={"file": ("sample_data.csv", f, "text/csv")})
    body = r.json()
    assert r.status_code == 200
    assert body["uploaded"] == 20
    assert body["errors_count"] == 0
    assert body["errors"] == []


def test_single_valid_row():
    status, body = upload(HEADER + VALID_ROW)
    assert status == 200
    assert body["uploaded"] == 1
    assert body["errors_count"] == 0


def test_header_only_returns_zeros():
    status, body = upload(HEADER)
    assert status == 200
    assert body["uploaded"] == 0
    assert body["errors_count"] == 0
    assert body["errors"] == []


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_invalid_marketplace_reported():
    row = "ORD-001,amazon,Кабель USB-C,3,450.00,120.00,delivered,2025-03-01\n"
    status, body = upload(HEADER + row)
    assert status == 200
    assert body["uploaded"] == 0
    assert body["errors_count"] == 1
    assert any("marketplace" in f for f in error_fields(body))


def test_invalid_status_reported():
    row = "ORD-001,ozon,Кабель USB-C,3,450.00,120.00,pending,2025-03-01\n"
    status, body = upload(HEADER + row)
    assert status == 200
    assert body["errors_count"] == 1
    assert any("status" in f for f in error_fields(body))


def test_zero_quantity_reported():
    row = "ORD-001,ozon,Кабель USB-C,0,450.00,120.00,delivered,2025-03-01\n"
    status, body = upload(HEADER + row)
    assert status == 200
    assert body["errors_count"] == 1
    assert any("quantity" in f for f in error_fields(body))


def test_negative_price_reported():
    row = "ORD-001,ozon,Кабель USB-C,3,-10.00,120.00,delivered,2025-03-01\n"
    status, body = upload(HEADER + row)
    assert status == 200
    assert body["errors_count"] == 1
    assert any("price" in f for f in error_fields(body))


def test_future_sold_at_reported():
    row = "ORD-001,ozon,Кабель USB-C,3,450.00,120.00,delivered,2099-01-01\n"
    status, body = upload(HEADER + row)
    assert status == 200
    assert body["errors_count"] == 1
    assert any("sold_at" in f for f in error_fields(body))


# ---------------------------------------------------------------------------
# Row numbers
# ---------------------------------------------------------------------------

def test_error_row_number_is_csv_line_number():
    # Row 2 = first data row (valid), row 3 = invalid
    valid = "ORD-001,ozon,Кабель USB-C,3,450.00,120.00,delivered,2025-03-01\n"
    bad = "ORD-002,amazon,Кабель USB-C,3,450.00,120.00,delivered,2025-03-01\n"
    status, body = upload(HEADER + valid + bad)
    assert status == 200
    assert body["errors"][0]["row"] == 3


def test_error_row_number_first_row():
    bad = "ORD-001,amazon,Кабель USB-C,3,450.00,120.00,delivered,2025-03-01\n"
    status, body = upload(HEADER + bad)
    assert body["errors"][0]["row"] == 2


# ---------------------------------------------------------------------------
# Mixed valid and invalid
# ---------------------------------------------------------------------------

def test_mixed_rows_counts():
    valid = "ORD-001,ozon,Кабель USB-C,3,450.00,120.00,delivered,2025-03-01\n"
    bad1 = "ORD-002,amazon,Bad,1,100.00,50.00,delivered,2025-03-01\n"
    bad2 = "ORD-003,ozon,Bad,0,100.00,50.00,delivered,2025-03-01\n"
    status, body = upload(HEADER + valid + bad1 + bad2)
    assert status == 200
    assert body["uploaded"] == 1
    assert body["errors_count"] == 2
    assert len(body["errors"]) == 2


def test_multiple_errors_on_one_row():
    # Both marketplace and status invalid
    row = "ORD-001,amazon,Bad,3,450.00,120.00,pending,2025-03-01\n"
    status, body = upload(HEADER + row)
    assert status == 200
    assert body["errors_count"] == 1
    fields = error_fields(body)
    assert any("marketplace" in f for f in fields)
    assert any("status" in f for f in fields)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_duplicate_rows_not_double_counted():
    status, body = upload(HEADER + VALID_ROW + VALID_ROW)
    assert status == 200
    assert body["uploaded"] == 1
    assert body["errors_count"] == 0


def test_duplicate_after_prior_upload():
    upload(HEADER + VALID_ROW)
    status, body = upload(HEADER + VALID_ROW)
    assert status == 200
    assert body["uploaded"] == 0
    assert body["errors_count"] == 0


# ---------------------------------------------------------------------------
# Invalid file
# ---------------------------------------------------------------------------

def test_non_csv_file_returns_422():
    r = client.post(
        BASE,
        files={"file": ("data.bin", b"\x00\x01\x02\x03binary\xff\xfe", "application/octet-stream")},
    )
    assert r.status_code == 422


def test_json_file_returns_422():
    json_bytes = b'{"order_id": "ORD-001", "marketplace": "ozon"}'
    r = client.post(BASE, files={"file": ("data.json", json_bytes, "application/json")})
    assert r.status_code == 422


def test_missing_columns_returns_422():
    status, body = upload("order_id,marketplace\nORD-001,ozon\n")
    assert status == 422


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

def test_response_shape():
    status, body = upload(HEADER + VALID_ROW)
    assert status == 200
    assert "uploaded" in body
    assert "errors_count" in body
    assert "errors" in body
    assert isinstance(body["errors"], list)
