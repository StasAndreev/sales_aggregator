import io
import logging
from datetime import date
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import ValidationError

from models.sales import AddSalesResponse, CsvRowError, FailedItem, Marketplace, Sale, SaleStatus, SalesListResponse, UploadCsvResponse
from services import storage

logger = logging.getLogger(__name__)

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

    if failed:
        logger.warning("POST /sales: %d/%d items failed validation", len(failed), len(items))

    added = storage.add_sales(valid)

    return AddSalesResponse(added=added, failed=failed)


_MAX_CSV_SIZE = 10 * 1024 * 1024
_REQUIRED_COLUMNS = {"order_id", "marketplace", "product_name", "quantity", "price", "cost_price", "status", "sold_at"}


@router.post("/upload-csv", response_model=UploadCsvResponse)
def upload_csv(file: UploadFile = File(...)) -> UploadCsvResponse:
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
