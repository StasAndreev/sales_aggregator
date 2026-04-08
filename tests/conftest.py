import csv

import pytest

from models.sales import Sale
from services import storage

CSV_PATH = "sample_data.csv"


@pytest.fixture(autouse=True)
def test_db(tmp_path):
    storage.DB_PATH = str(tmp_path / "test_sales.db")
    storage.init_db()
    yield


@pytest.fixture
def seeded_db(test_db):
    sales = []
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            sales.append(Sale.model_validate(row))
    storage.add_sales(sales)
