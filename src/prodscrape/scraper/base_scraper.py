from src.prodscrape.browser.client import PooledPlaywrightClient
from typing import Dict, Any
from src.logger import get_logger


class Scraper:
    """Base Class used by other Scraper Classes"""

    def __init__(self, client: PooledPlaywrightClient, logger_name: str, url: str):
        self.client = client
        self.scraped_data = []
        self.log = get_logger(logger_name)
        self.url = url

    async def scrape_product_details(self, product_name: str) -> Dict[str, Any]:
        """Override this method to implement product scraping logic"""
        pass
