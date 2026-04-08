from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, field_validator


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
    uploaded: int
    errors_count: int
    errors: list[CsvRowError]


class AddSalesResponse(BaseModel):
    added: int
    failed: list[FailedItem]


class SaleResponse(BaseModel):
    order_id: str
    marketplace: str
    product_name: str
    quantity: int
    price: float
    cost_price: float
    status: str
    sold_at: str


class SalesListResponse(BaseModel):
    items: list[SaleResponse]
    total: int