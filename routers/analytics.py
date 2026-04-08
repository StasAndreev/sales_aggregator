from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from models.analytics import GroupedMetricsResponse, TopProductResponse
from models.sales import Marketplace
from services import analytics
from services.currency import CurrencyUnavailableError, get_usd_rate

router = APIRouter(prefix="/analytics", tags=["analytics"])

_MONEY_FIELDS = ("total_revenue", "total_cost", "gross_profit", "avg_order_value")


@router.get("/summary", response_model=list[GroupedMetricsResponse])
def get_summary(
    date_from: date,
    date_to: date,
    marketplace: Marketplace | None = None,
    group_by: Literal["marketplace", "date", "status"] | None = None,
) -> list[GroupedMetricsResponse]:
    results = analytics.get_summary(
        iso_date_from=date_from.isoformat(),
        iso_date_to=date_to.isoformat(),
        marketplace=marketplace.value if marketplace else None,
        group_by=group_by,
    )
    return [GroupedMetricsResponse(**row) for row in results]


@router.get("/summary-usd", response_model=list[GroupedMetricsResponse])
def get_summary_usd(
    date_from: date,
    date_to: date,
    marketplace: Marketplace | None = None,
    group_by: Literal["marketplace", "date", "status"] | None = None,
) -> list[GroupedMetricsResponse]:
    try:
        rate = get_usd_rate()
    except CurrencyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    results = analytics.get_summary(
        iso_date_from=date_from.isoformat(),
        iso_date_to=date_to.isoformat(),
        marketplace=marketplace.value if marketplace else None,
        group_by=group_by,
    )

    converted = []
    for row in results:
        item = dict(row)
        for field in _MONEY_FIELDS:
            item[field] = round(item[field] / rate, 2)
        converted.append(GroupedMetricsResponse(**item))
    return converted


@router.get("/top-products", response_model=list[TopProductResponse])
def get_top_products(
    date_from: date,
    date_to: date,
    sort_by: Literal["revenue", "quantity", "profit"] = "revenue",
    limit: int = Query(default=10, ge=1),
) -> list[TopProductResponse]:
    results = analytics.get_top_products(
        iso_date_from=date_from.isoformat(),
        iso_date_to=date_to.isoformat(),
        sort_by=sort_by,
        limit=limit,
    )
    return [TopProductResponse(**row) for row in results]
