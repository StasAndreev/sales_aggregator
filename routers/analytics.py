import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from models.analytics import GroupedMetricsResponse, TopProductResponse
from models.sales import Marketplace
from services import analytics
from services.currency import CurrencyUnavailableError, get_usd_rate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_MONEY_FIELDS = ("total_revenue", "total_cost", "gross_profit", "avg_order_value")


@router.get("/summary", response_model=list[GroupedMetricsResponse], summary="Sales summary")
def get_summary(
    date_from: date = Query(description="Start date inclusive (YYYY-MM-DD)"),
    date_to: date = Query(description="End date inclusive (YYYY-MM-DD)"),
    marketplace: Marketplace | None = Query(default=None, description="Filter by marketplace"),
    group_by: Literal["marketplace", "date", "status"] | None = Query(default=None, description="Group results by this field; omit for a single aggregate row"),
) -> list[GroupedMetricsResponse]:
    """
    Return aggregated sales metrics for a date range.

    Without `group_by`, returns a single row with totals across the entire period.
    With `group_by`, returns one row per distinct value of the chosen field.
    """
    results = analytics.get_summary(
        iso_date_from=date_from.isoformat(),
        iso_date_to=date_to.isoformat(),
        marketplace=marketplace.value if marketplace else None,
        group_by=group_by,
    )
    return [GroupedMetricsResponse(**row) for row in results]


@router.get("/summary-usd", response_model=list[GroupedMetricsResponse], summary="Sales summary in USD")
def get_summary_usd(
    date_from: date = Query(description="Start date inclusive (YYYY-MM-DD)"),
    date_to: date = Query(description="End date inclusive (YYYY-MM-DD)"),
    marketplace: Marketplace | None = Query(default=None, description="Filter by marketplace"),
    group_by: Literal["marketplace", "date", "status"] | None = Query(default=None, description="Group results by this field; omit for a single aggregate row"),
) -> list[GroupedMetricsResponse]:
    """
    Same as `/summary` but all monetary fields (`total_revenue`, `total_cost`, `gross_profit`,
    `avg_order_value`) are converted from RUB to USD using the live CBR exchange rate.

    Returns 503 if the CBR API is unavailable and no cached rate exists.
    """
    try:
        rate = get_usd_rate()
    except CurrencyUnavailableError as exc:
        logger.warning("USD rate unavailable: %s", exc)
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


@router.get("/top-products", response_model=list[TopProductResponse], summary="Top products")
def get_top_products(
    date_from: date = Query(description="Start date inclusive (YYYY-MM-DD)"),
    date_to: date = Query(description="End date inclusive (YYYY-MM-DD)"),
    sort_by: Literal["revenue", "quantity", "profit"] = Query(default="revenue", description="Metric to rank products by"),
    limit: int = Query(default=10, ge=1, description="Maximum number of products to return"),
) -> list[TopProductResponse]:
    """
    Return the top N delivered products ranked by the chosen metric.

    Only `delivered` orders contribute to revenue, quantity, and profit calculations.
    """
    results = analytics.get_top_products(
        iso_date_from=date_from.isoformat(),
        iso_date_to=date_to.isoformat(),
        sort_by=sort_by,
        limit=limit,
    )
    return [TopProductResponse(**row) for row in results]
