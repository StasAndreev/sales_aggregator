from datetime import date
from typing import Literal

from fastapi import APIRouter

from models.analytics import GroupedMetricsResponse
from models.sales import Marketplace
from services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


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
