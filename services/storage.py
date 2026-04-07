import sqlite3
from contextlib import contextmanager
from models.sale import Sale

DB_PATH = "sales.db"

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS sales (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT    NOT NULL,
    marketplace TEXT    NOT NULL,
    product_name TEXT   NOT NULL,
    quantity    INTEGER NOT NULL,
    price       TEXT    NOT NULL,
    cost_price  TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    sold_at     TEXT    NOT NULL,
    UNIQUE (order_id, marketplace)
)
"""


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute(_INIT_SQL)


def add_sales(sales: list[Sale]) -> int:
    rows = [
        (
            s.order_id,
            s.marketplace.value,
            s.product_name,
            s.quantity,
            str(s.price),
            str(s.cost_price),
            s.status.value,
            s.sold_at.isoformat(),
        )
        for s in sales
    ]
    with _conn() as con:
        con.executemany(
            "INSERT INTO sales (order_id, marketplace, product_name, quantity, price, cost_price, status, sold_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)
