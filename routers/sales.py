from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from models.sale import Sale
from services import storage

router = APIRouter(prefix="/sales", tags=["sales"])


class FailedItem(BaseModel):
    index: int
    errors: list[dict]


class AddSalesResponse(BaseModel):
    added: int
    failed: list[FailedItem]


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

    added = storage.add_sales(valid) if valid else 0

    return AddSalesResponse(added=added, failed=failed)
