import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.logger import get_logger
from src.prodscrape.scraper.amazon_scraper import AmazonScraper
from src.prodscrape.browser.client import get_pool
from src.config.db import connect_db, disconnect_db, postgres_connection_pool
import uvloop

log = get_logger("scheduler")


async def get_prodoct_prices():
    try:
        await connect_db()
        pool = get_pool(max_clients=5)
        client1 = await pool.get_client("firefox")

        as1 = AmazonScraper(
            client1,
            "https://www.amazon.in",
        )

        async with postgres_connection_pool().acquire() as conn:
            query = """
            SELECT * FROM amazon_products
            WHERE is_deleted=False
            """
            products = await conn.fetch(query)

        coros = []
        for product in products:
            coros.append(as1.scrape_product_price(product["asin"]))

        resp = await asyncio.gather(*coros)
        print(resp)
    finally:
        stats = await pool.get_pool_stats()
        log.info(f"\nPool stats: {stats}")

        await pool.close_all()
        await disconnect_db()


scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(get_prodoct_prices, "interval", minutes=10)


async def main():
    try:
        scheduler.start()
        log.info("Scheduler started")
        while True:
            await asyncio.sleep(1000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Scheduler stopped")


if __name__ == "__main__":
    try:
        uvloop.run(main())
    except Exception as e:
        log.error(e)
