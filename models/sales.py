from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Marketplace(str, Enum):
    ozon = "ozon"
    wildberries = "wildberries"
    yandex_market = "yandex_market"


class SaleStatus(str, Enum):
    delivered = "delivered"
    returned = "returned"
    cancelled = "cancelled"


class Sale(BaseModel):
    order_id: str
    marketplace: Marketplace
    product_name: str
    quantity: int = Field(ge=1)
    price: Decimal = Field(gt=0, decimal_places=2)
    cost_price: Decimal = Field(gt=0, decimal_places=2)
    status: SaleStatus
    sold_at: date

    @field_validator("sold_at")
    @classmethod
    def check_sold_at_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("sold_at cannot be in the future")
        return v


class FailedItem(BaseModel):
    index: int
    errors: list[dict]


class CsvRowError(BaseModel):
    row: int
    errors: list[dict]


class UploadCsvResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "uploaded": 18,
        "errors_count": 2,
        "errors": [
            {"row": 5, "errors": [{"field": "marketplace", "message": "Input should be 'ozon', 'wildberries' or 'yandex_market'"}]},
            {"row": 12, "errors": [{"field": "quantity", "message": "Input should be greater than or equal to 1"}]},
        ],
    }})

    uploaded: int
    errors_count: int
    errors: list[CsvRowError]


class AddSalesResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "added": 1,
        "failed": [
            {"index": 1, "errors": [{"field": "marketplace", "message": "Input should be 'ozon', 'wildberries' or 'yandex_market'"}]}
        ],
    }})

    added: int
    failed: list[FailedItem]


class SaleResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "order_id": "ORD-001",
        "marketplace": "ozon",
        "product_name": "Кабель USB-C",
        "quantity": 3,
        "price": 450.0,
        "cost_price": 120.0,
        "status": "delivered",
        "sold_at": "2025-03-01",
    }})

    order_id: str
    marketplace: str
    product_name: str
    quantity: int
    price: float
    cost_price: float
    status: str
    sold_at: str


class SalesListResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "items": [
            {
                "order_id": "ORD-001",
                "marketplace": "ozon",
                "product_name": "Кабель USB-C",
                "quantity": 3,
                "price": 450.0,
                "cost_price": 120.0,
                "status": "delivered",
                "sold_at": "2025-03-01",
            }
        ],
        "total": 1,
    }})

    items: list[SaleResponse]
    total: int