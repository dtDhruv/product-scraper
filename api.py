from fastapi.responses import JSONResponse

import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.config.db import connect_db, disconnect_db, postgres_connection_pool
from starlette import status

from src.logger import get_logger
from src.prodscrape.api.amazon_api import AmazonRouter
# from apscheduler.schedulers.asyncio import AsyncIOScheduler

# scheduler = AsyncIOScheduler(timezone="UTC")

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    # scheduler.start()
    yield
    await disconnect_db()


app = FastAPI(title="Product Scraper API hooks", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def response_formatter(request: Request, call_next):
    """formats exception response as needed by hasura client"""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        log.exception(e)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Bad request"}
        )


app.include_router(
    AmazonRouter(pool_provider=postgres_connection_pool),
    prefix="/api/v1",
    tags=["amazon"],
)

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
    )
