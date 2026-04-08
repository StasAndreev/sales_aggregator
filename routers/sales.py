from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from models.sales import Marketplace, Sale, SaleStatus
from models.sales import AddSalesResponse, FailedItem, SalesListResponse
from services import storage

router = APIRouter(prefix="/sales", tags=["sales"])


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
        iso_date_from=date_from.isoformat() if date_from else None,
        iso_date_to=date_to.isoformat() if date_to else None,
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
