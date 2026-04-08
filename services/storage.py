import logging
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from models.sales import Sale

logger = logging.getLogger(__name__)

DB_PATH = "sales.db"

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS sales (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     TEXT    NOT NULL,
    marketplace  TEXT    NOT NULL,
    product_name TEXT    NOT NULL,
    quantity     INTEGER NOT NULL,
    price        TEXT    NOT NULL,
    cost_price   TEXT    NOT NULL,
    status       TEXT    NOT NULL,
    sold_at      TEXT    NOT NULL,
    UNIQUE (order_id, marketplace)
);
CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales(sold_at);
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
    logger.info("Initialising database at %s", DB_PATH)
    with _conn() as con:
        con.executescript(_INIT_SQL)
    logger.info("Database ready")


def get_sales(
    marketplace: str | None = None,
    status: str | None = None,
    iso_date_from: str | None = None,
    iso_date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    sql_conditions: list[str] = []
    sql_params: list = []

    if marketplace:
        sql_conditions.append("marketplace = ?")
        sql_params.append(marketplace)
    if status:
        sql_conditions.append("status = ?")
        sql_params.append(status)
    if iso_date_from:
        sql_conditions.append("sold_at >= ?")
        sql_params.append(iso_date_from)
    if iso_date_to:
        sql_conditions.append("sold_at <= ?")
        sql_params.append(iso_date_to)

    sql_where = f"WHERE {' AND '.join(sql_conditions)}" if sql_conditions else ""

    with _conn() as con:
        total = con.execute(f"SELECT COUNT(*) FROM sales {sql_where}", sql_params).fetchone()[0]
        rows = con.execute(
            f"SELECT * FROM sales {sql_where} ORDER BY id LIMIT ? OFFSET ?",
            sql_params + [page_size, (page - 1) * page_size],
        ).fetchall()

    return [dict(row) for row in rows], total


def get_raw_sales(
    iso_date_from: str,
    iso_date_to: str,
    marketplace: str | None = None,
) -> list[dict]:
    sql_where = "WHERE sold_at >= ? AND sold_at <= ?"
    sql_params: list = [iso_date_from, iso_date_to]

    if marketplace:
        sql_where += " AND marketplace = ?"
        sql_params.append(marketplace)

    with _conn() as con:
        rows = con.execute(
            f"SELECT order_id, marketplace, product_name, quantity, price, cost_price, status, sold_at FROM sales {sql_where}",
            sql_params,
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["price"] = Decimal(d["price"])
        d["cost_price"] = Decimal(d["cost_price"])
        result.append(d)
    return result


def add_sales(sales: list[Sale]) -> int:
    logger.debug("Inserting %d sale rows", len(sales))
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
        cur = con.executemany(
            "INSERT OR IGNORE INTO sales (order_id, marketplace, product_name, quantity, price, cost_price, status, sold_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    logger.info("Inserted %d/%d rows (duplicates ignored)", cur.rowcount, len(rows))
    return cur.rowcount
