import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.logging_config import configure_logging
from routers import analytics, sales
from services.storage import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting up")
    init_db()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Sales Aggregator",
    description=(
        "Aggregates marketplace sales data from Ozon, Wildberries, and Yandex Market. "
        "Supports batch ingestion via JSON or CSV upload, pagination, filtering, "
        "and analytics with optional USD conversion."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(sales.router)
app.include_router(analytics.router)
