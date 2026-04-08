from pydantic import BaseModel


class GroupedMetricsResponse(BaseModel):
    group: str
    total_revenue: float
    total_cost: float
    gross_profit: float
    margin_percent: float
    total_orders: int
    avg_order_value: float
    return_rate: float


class TopProductResponse(BaseModel):
    product_name: str
    revenue: float
    quantity: int
    profit: float
