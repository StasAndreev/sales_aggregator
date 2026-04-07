from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ValidationError

from models.sale import Marketplace, Sale, SaleStatus
from services import storage

router = APIRouter(prefix="/sales", tags=["sales"])


class FailedItem(BaseModel):
    index: int
    errors: list[dict]


class AddSalesResponse(BaseModel):
    added: int
    failed: list[FailedItem]


class SaleItem(BaseModel):
    order_id: str
    marketplace: str
    product_name: str
    quantity: int
    price: str
    cost_price: str
    status: str
    sold_at: str


class SalesListResponse(BaseModel):
    items: list[SaleItem]
    total: int


@router.get("", response_model=SalesListResponse)
def list_sales(
    marketplace: Marketplace | None = None,
    status: SaleStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
) -> SalesListResponse:
    items, total = storage.get_sales(
        marketplace=marketplace.value if marketplace else None,
        status=status.value if status else None,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        page=page,
        page_size=page_size,
    )
    return SalesListResponse(items=items, total=total)


@router.post("", response_model=AddSalesResponse)
def create_sales(items: list[Any]) -> AddSalesResponse:
    if not items:
        raise HTTPException(status_code=422, detail="Request body must contain at least one sale")

    valid: list[Sale] = []
    failed: list[FailedItem] = []

    for i, item in enumerate(items):
        try:
            valid.append(Sale.model_validate(item))
        except ValidationError as e:
            failed.append(FailedItem(
                index=i,
                errors=[
                    {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
                    for err in e.errors()
                ],
            ))

    added = storage.add_sales(valid)

    return AddSalesResponse(added=added, failed=failed)
