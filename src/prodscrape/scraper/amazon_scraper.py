from src.prodscrape.scraper.base_scraper import Scraper
from src.prodscrape.browser.client import PooledPlaywrightClient
import asyncio
from bs4 import BeautifulSoup


class AmazonScraper(Scraper):
    def __init__(self, client: PooledPlaywrightClient, url: str):
        super().__init__(client=client, logger_name="AmazonScraper", url=url)

    async def scrape_product_price(self, asin):
        self.log.info(f"Fetching product details for product with asin number {asin}")
        try:
            product_page = self.url + f"/dp/{asin}?th=1"
            await self.client.goto(url=product_page)
            await asyncio.sleep(2)
            page_html = await self.client.page.content()

            soup = BeautifulSoup(page_html, "lxml")
            div = soup.find("div", {"id": "corePriceDisplay_desktop_feature_div"})
            price = div.find("span", {"class": "a-price-whole"})
            self.log.info(f"Successfully fetched price for product with ASIN {asin}")
            return price.text

        except Exception as e:
            self.log.error(f"Failed to fetch price for product with ASIN {asin}")
            self.log.exception(e)
