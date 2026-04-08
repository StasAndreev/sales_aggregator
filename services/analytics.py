import pandas as pd

from services import storage

_GROUP_BY_COLUMN = {"marketplace": "marketplace", "date": "sold_at", "status": "status"}

_EMPTY_METRICS = {
    "total_revenue": 0.0, "total_cost": 0.0, "gross_profit": 0.0,
    "margin_percent": 0.0, "total_orders": 0, "avg_order_value": 0.0, "return_rate": 0.0,
}


def _compute_metrics(df: pd.DataFrame) -> dict:
    delivered = df[df["status"] == "delivered"]
    returned = df[df["status"] == "returned"]

    revenue = float((delivered["price"] * delivered["quantity"]).sum())
    cost = float((delivered["cost_price"] * delivered["quantity"]).sum())
    gross_profit = revenue - cost
    total_orders = len(df)
    del_ret = len(delivered) + len(returned)

    return {
        "total_revenue": round(revenue, 2),
        "total_cost": round(cost, 2),
        "gross_profit": round(gross_profit, 2),
        "margin_percent": round(gross_profit / revenue * 100, 2) if revenue else 0.0,
        "total_orders": total_orders,
        "avg_order_value": round(revenue / total_orders, 2) if total_orders else 0.0,
        "return_rate": round(len(returned) / del_ret * 100, 2) if del_ret else 0.0,
    }


def get_summary(
    iso_date_from: str,
    iso_date_to: str,
    marketplace: str | None = None,
    group_by: str | None = None,
) -> list[dict]:
    if group_by is not None and group_by not in _GROUP_BY_COLUMN:
        raise ValueError(f"Invalid group_by value: {group_by!r}")

    rows = storage.get_raw_sales(
        iso_date_from=iso_date_from,
        iso_date_to=iso_date_to,
        marketplace=marketplace,
    )

    if not rows:
        return [{"group": "", **_EMPTY_METRICS}]

    df = pd.DataFrame(rows)

    if group_by is None:
        return [{"group": "", **_compute_metrics(df)}]

    col = _GROUP_BY_COLUMN[group_by]
    return [
        {"group": str(key), **_compute_metrics(group_df)}
        for key, group_df in df.groupby(col)
    ]


def get_top_products(
    iso_date_from: str,
    iso_date_to: str,
    sort_by: str = "revenue",
    limit: int = 10,
) -> list[dict]:
    rows = storage.get_raw_sales(iso_date_from=iso_date_from, iso_date_to=iso_date_to)

    if not rows:
        return []

    df = pd.DataFrame(rows)
    delivered = df[df["status"] == "delivered"].copy()

    if delivered.empty:
        return []

    delivered["price"] = delivered["price"].astype(float)
    delivered["cost_price"] = delivered["cost_price"].astype(float)
    delivered["revenue"] = delivered["price"] * delivered["quantity"]
    delivered["cost"] = delivered["cost_price"] * delivered["quantity"]

    grouped = delivered.groupby("product_name").agg(
        revenue=("revenue", "sum"),
        quantity=("quantity", "sum"),
        cost=("cost", "sum"),
    )
    grouped["profit"] = grouped["revenue"] - grouped["cost"]

    top = grouped.nlargest(limit, sort_by).reset_index()

    return [
        {
            "product_name": row["product_name"],
            "revenue": round(float(row["revenue"]), 2),
            "quantity": int(row["quantity"]),
            "profit": round(float(row["profit"]), 2),
        }
        for _, row in top.iterrows()
    ]
