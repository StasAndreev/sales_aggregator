from pydantic import BaseModel, ConfigDict


class GroupedMetricsResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "group": "ozon",
        "total_revenue": 54000.0,
        "total_cost": 14400.0,
        "gross_profit": 39600.0,
        "margin_percent": 73.33,
        "total_orders": 120,
        "avg_order_value": 450.0,
        "return_rate": 4.17,
    }})

    group: str
    total_revenue: float
    total_cost: float
    gross_profit: float
    margin_percent: float
    total_orders: int
    avg_order_value: float
    return_rate: float


class TopProductResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "product_name": "Кабель USB-C",
        "revenue": 54000.0,
        "quantity": 120,
        "profit": 39600.0,
    }})

    product_name: str
    revenue: float
    quantity: int
    profit: float
