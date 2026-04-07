import pytest
from services import storage


@pytest.fixture(autouse=True)
def test_db(tmp_path):
    storage.DB_PATH = str(tmp_path / "test_sales.db")
    storage.init_db()
    yield
