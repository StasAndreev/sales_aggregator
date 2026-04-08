import io
import logging
from datetime import date
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from pydantic import ValidationError

from models.sales import AddSalesResponse, CsvRowError, FailedItem, Marketplace, Sale, SaleStatus, SalesListResponse, UploadCsvResponse
from services import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("", response_model=SalesListResponse, summary="List sales")
def list_sales(
    marketplace: Marketplace | None = Query(default=None, description="Filter by marketplace"),
    status: SaleStatus | None = Query(default=None, description="Filter by order status"),
    date_from: date | None = Query(default=None, description="Start date inclusive (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="End date inclusive (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, description="Results per page"),
) -> SalesListResponse:
    """
    Return a paginated list of sales records. All filters are optional and combinable.
    """
    items, total = storage.get_sales(
        marketplace=marketplace.value if marketplace else None,
        status=status.value if status else None,
        iso_date_from=date_from.isoformat() if date_from else None,
        iso_date_to=date_to.isoformat() if date_to else None,
        page=page,
        page_size=page_size,
    )
    return SalesListResponse(items=items, total=total)


_SALE_EXAMPLE = {
    "order_id": "ORD-001",
    "marketplace": "ozon",
    "product_name": "Кабель USB-C",
    "quantity": 3,
    "price": 450.00,
    "cost_price": 120.00,
    "status": "delivered",
    "sold_at": "2025-03-01",
}


@router.post("", response_model=AddSalesResponse, summary="Create sales")
def create_sales(
    items: Annotated[list[Any], Body(
        openapi_examples={
            "single": {
                "summary": "Single valid sale",
                "value": [_SALE_EXAMPLE],
            },
            "batch_with_error": {
                "summary": "Batch — one valid, one with invalid marketplace",
                "value": [
                    _SALE_EXAMPLE,
                    {**_SALE_EXAMPLE, "order_id": "ORD-002", "marketplace": "amazon"},
                ],
            },
        }
    )],
) -> AddSalesResponse:
    """
    Submit one or more sales records in a single request.

    Valid items are inserted; invalid items are returned in `failed` with field-level error messages.
    Duplicate `(order_id, marketplace)` pairs are silently ignored and not counted in `added`.
    """
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

    if failed:
        logger.warning("POST /sales: %d/%d items failed validation", len(failed), len(items))

    added = storage.add_sales(valid)

    return AddSalesResponse(added=added, failed=failed)


_MAX_CSV_SIZE = 10 * 1024 * 1024
_REQUIRED_COLUMNS = {"order_id", "marketplace", "product_name", "quantity", "price", "cost_price", "status", "sold_at"}


@router.post("/upload-csv", response_model=UploadCsvResponse, summary="Upload sales CSV")
def upload_csv(
    file: UploadFile = File(..., description="CSV file with columns: order_id, marketplace, product_name, quantity, price, cost_price, status, sold_at"),
) -> UploadCsvResponse:
    """
    Upload a CSV file containing sales records.

    Valid rows are inserted; invalid rows are collected in `errors` with the CSV line number and
    field-level messages. Duplicate `(order_id, marketplace)` pairs are silently ignored.
    Maximum file size: 10 MB.
    """
    contents = file.file.read()
    logger.info("CSV upload: filename=%r size=%d bytes", file.filename, len(contents))
    if len(contents) > _MAX_CSV_SIZE:
        logger.warning("CSV upload rejected: size %d exceeds %d byte limit", len(contents), _MAX_CSV_SIZE)
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    try:
        df = pd.read_csv(io.BytesIO(contents), dtype=str, keep_default_na=False)
    except Exception as e:
        logger.warning("CSV parse failed: %s", e)
        raise HTTPException(status_code=422, detail=f"Failed to read CSV file: {e}")

    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        logger.warning("CSV missing required columns: %s", sorted(missing))
        raise HTTPException(status_code=422, detail=f"Missing required columns: {sorted(missing)}")

    valid: list[Sale] = []
    errors: list[CsvRowError] = []

    for idx, row in df.iterrows():
        row_num = int(idx) + 2
        try:
            valid.append(Sale.model_validate(row.to_dict()))
        except ValidationError as e:
            errors.append(CsvRowError(
                row=row_num,
                errors=[
                    {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
                    for err in e.errors()
                ],
            ))

    if errors:
        logger.warning("CSV upload: %d rows failed validation", len(errors))

    added = storage.add_sales(valid)
    logger.info("CSV upload complete: inserted %d, errors %d", added, len(errors))
    return UploadCsvResponse(uploaded=added, errors_count=len(errors), errors=errors)
