from contextlib import asynccontextmanager

from fastapi import FastAPI

from routers import sales
from services.storage import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sales Aggregator", lifespan=lifespan)

app.include_router(sales.router)
