import asyncpg
from dotenv import load_dotenv
import os
from src.logger import get_logger

log = get_logger("db")

load_dotenv(override=True)

_pool = None


async def connect_db():
    global _pool
    _pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=int(os.getenv("DB_MIN_SIZE", 1)),
        max_size=int(os.getenv("DB_MAX_SIZE", 20)),
        command_timeout=60.0,
        max_inactive_connection_lifetime=300.0,
        server_settings={"application_name": "future-konnect-apis"},
    )


async def disconnect_db():
    global _pool
    if _pool:
        await _pool.close()


def postgres_connection_pool() -> asyncpg.pool.Pool:
    if not _pool:
        log.error("Database connection not established")
    return _pool


async def test():
    await connect_db()
    async with postgres_connection_pool().acquire() as conn:
        query = """
        SELECT * FROM amazon_products
        """
        resp = await conn.fetch(query)
    print(resp[0]["asin"])
    await disconnect_db()


if __name__ == "__main__":
    import asyncio

    asyncio.run(test())
