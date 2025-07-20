import asyncio
from src.prodscrape.scraper.amazon_scraper import AmazonScraper
from src.prodscrape.browser.client import get_pool
from src.logger import get_logger


async def main():
    log = get_logger("app")
    try:
        pool = get_pool(max_clients=3)
        client1 = await pool.get_client("firefox")

        as1 = AmazonScraper(
            client1,
            "https://www.amazon.in",
        )

        coros = []
        coros.append(as1.scrape_product_price("B0CCZ1L489"))
        resp = await asyncio.gather(*coros)
        print(resp)

    finally:
        stats = await pool.get_pool_stats()
        log.info(f"\nPool stats: {stats}")

        await pool.close_all()


asyncio.run(main())
