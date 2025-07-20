from fastapi import APIRouter, Depends
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from typing import Callable
from asyncpg import Pool
from src.prodscrape.api.auth import get_current_active_user, User

amazon_router = APIRouter(prefix="/amazon")


class AmazonProduct(BaseModel):
    asin: str


class AmazonRouter(APIRouter):
    def __init__(self, pool_provider: Callable[[], Pool]):
        super().__init__(prefix="/amazon")
        self.pool_provider = pool_provider

        self.add_api_route(
            "/add-product",
            self.add_product_to_db,
            methods=["POST"],
        )

    async def add_product_to_db(
        self,
        request: AmazonProduct,
        current_user: User = Depends(get_current_active_user),
    ):
        if not request.asin:
            return JSONResponse(
                status_code=400, content={"Error": "Invalid Data Input"}
            )

        pool = self.pool_provider()
        async with pool.acquire() as conn:
            query = """
            INSERT INTO amazon_products (asin)
            VALUES ($1)
            ON CONFLICT (asin) DO NOTHING;
            """
            await conn.execute(query, request.asin)

        return JSONResponse(
            status_code=200,
            content={"message": "Product added successfully", "asin": request.asin},
        )
