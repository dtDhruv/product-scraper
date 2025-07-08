# playwright_pool.py
import asyncio
import time
import uuid
from typing import Dict, Optional, Set, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)


class PooledPlaywrightClient:
    """
    A Playwright client that's managed by the pool
    This is what gets passed to other classes
    """

    def __init__(
        self,
        client_id: str,
        browser: Browser,
        context: BrowserContext,
        page: Page,
        browser_type: str,
        pool_manager: "PlaywrightPool",
    ):
        self.client_id = client_id
        self.browser = browser
        self.context = context
        self.page = page
        self.browser_type = browser_type
        self._pool_manager = pool_manager
        self._is_returned = False

    # Direct access to playwright objects
    def get_page(self) -> Page:
        """Get the page instance"""
        return self.page

    def get_context(self) -> BrowserContext:
        """Get the context instance"""
        return self.context

    def get_browser(self) -> Browser:
        """Get the browser instance"""
        return self.browser

    # Common helper methods
    async def goto(self, url: str, **options):
        """Navigate to URL"""
        default_options = {"timeout": 50000}
        return await self.page.goto(url, **{**default_options, **options})

    async def wait_for_selector(self, selector: str, **options):
        """Wait for selector"""
        default_options = {"timeout": 50000, "state": "visible"}
        return await self.page.wait_for_selector(
            selector, **{**default_options, **options}
        )

    async def click(self, selector: str, **options):
        """Click element"""
        return await self.page.click(selector, **options)

    async def fill(self, selector: str, value: str, **options):
        """Fill input"""
        return await self.page.fill(selector, value, **options)

    async def get_text(self, selector: str) -> str:
        """Get text content"""
        element = await self.page.query_selector(selector)
        return await element.text_content() if element else ""

    async def screenshot(self, **options) -> bytes:
        """Take screenshot"""
        default_options = {"full_page": True, "type": "png"}
        return await self.page.screenshot(**{**default_options, **options})

    async def evaluate(self, expression: str, *args):
        """Evaluate JavaScript"""
        return await self.page.evaluate(expression, *args)

    async def wait_for_load_state(self, state: str = "networkidle", **options):
        """Wait for load state"""
        return await self.page.wait_for_load_state(state, **options)

    async def new_page(self) -> Page:
        """Create new page in same context"""
        return await self.context.new_page()

    # Pool management
    async def return_to_pool(self):
        """Return this client back to the pool"""
        if not self._is_returned:
            await self._pool_manager.return_client(self.client_id)
            self._is_returned = True

    def is_returned(self) -> bool:
        """Check if client has been returned to pool"""
        return self._is_returned

    # Context manager support
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.return_to_pool()

    def __repr__(self):
        return f"PooledPlaywrightClient(id={self.client_id[:8]}, browser={self.browser_type}, returned={self._is_returned})"


@dataclass
class ClientInfo:
    """Internal information about a client in the pool"""

    client_id: str
    browser: Browser
    context: BrowserContext
    page: Page
    browser_type: str
    created_at: float
    last_used: float
    in_use: bool = False
    use_count: int = 0


class PlaywrightPool:
    """
    Manages a pool of Playwright browser instances for efficient reuse
    Returns actual client instances that can be passed to other classes
    """

    def __init__(
        self, max_clients: int = 5, max_idle_time: int = 300, cleanup_interval: int = 60
    ):
        self.max_clients = max_clients
        self.max_idle_time = max_idle_time
        self.cleanup_interval = cleanup_interval

        self.playwright: Optional[Playwright] = None
        self.clients: Dict[str, ClientInfo] = {}
        self.available_clients: Set[str] = set()
        self.client_queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_initialized = False

        # Default configuration
        self.default_config = {
            "headless": False,
            "timeout": 50000,
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "ignore_https_errors": True,
            "args": [
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        }

    async def initialize(self):
        """Initialize the playwright instance and start cleanup task"""
        if not self.is_initialized:
            self.playwright = await async_playwright().start()
            # self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.is_initialized = True
            print(f"PlaywrightPool initialized with Max Clients: {self.max_clients}")

    async def _create_client_info(
        self, browser_type: str = "chromium", **options
    ) -> ClientInfo:
        """Create a new browser client info"""
        if not self.playwright:
            await self.initialize()

        client_id = str(uuid.uuid4())

        # Merge options with defaults
        launch_options = {**self.default_config, **options}
        args = launch_options.pop("args", self.default_config["args"])
        viewport = launch_options.pop("viewport", self.default_config["viewport"])
        user_agent = launch_options.pop("user_agent", self.default_config["user_agent"])
        ignore_https_errors = launch_options.pop(
            "ignore_https_errors", self.default_config["ignore_https_errors"]
        )
        timeout = launch_options.pop("timeout", self.default_config["timeout"])

        # Launch browser
        if browser_type.lower() == "firefox":
            browser = await self.playwright.firefox.launch(args=args, **launch_options)
        elif browser_type.lower() in ["webkit", "safari"]:
            browser = await self.playwright.webkit.launch(args=args, **launch_options)
        else:  # chromium default
            browser = await self.playwright.chromium.launch(args=args, **launch_options)

        # Create context and page
        context = await browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            ignore_https_errors=ignore_https_errors,
        )
        page = await context.new_page()
        page.set_default_timeout(timeout)

        client_info = ClientInfo(
            client_id=client_id,
            browser=browser,
            context=context,
            page=page,
            browser_type=browser_type,
            created_at=time.time(),
            last_used=time.time(),
        )

        print(f"Created new {browser_type} client: {client_id[:8]}")
        return client_info

    async def get_client(
        self, browser_type: str = "chromium", **options
    ) -> PooledPlaywrightClient:
        """
        Get an available client from the pool or create a new one
        Returns a PooledPlaywrightClient instance that can be passed to other classes
        """
        async with self.lock:
            # Try to find an available client with matching browser type
            available_client_id = None
            for client_id in list(self.available_clients):
                client_info = self.clients[client_id]
                if client_info.browser_type == browser_type and not client_info.in_use:
                    available_client_id = client_id
                    break

            if available_client_id:
                # Reuse existing client
                client_info = self.clients[available_client_id]
                client_info.in_use = True
                client_info.last_used = time.time()
                client_info.use_count += 1
                self.available_clients.remove(available_client_id)

                pooled_client = PooledPlaywrightClient(
                    client_info.client_id,
                    client_info.browser,
                    client_info.context,
                    client_info.page,
                    client_info.browser_type,
                    self,
                )

                print(
                    f"♻️  Reusing {browser_type} client: {available_client_id[:8]} (used {client_info.use_count} times)"
                )
                return pooled_client

            # Create new client if under limit
            if len(self.clients) < self.max_clients:
                client_info = await self._create_client_info(browser_type, **options)
                client_info.in_use = True
                self.clients[client_info.client_id] = client_info

                pooled_client = PooledPlaywrightClient(
                    client_info.client_id,
                    client_info.browser,
                    client_info.context,
                    client_info.page,
                    client_info.browser_type,
                    self,
                )

                return pooled_client

            # Pool is full, wait for a client to become available
            print(
                f"Pool full ({len(self.clients)}/{self.max_clients}), waiting for available client..."
            )

        # Wait outside the lock
        while True:
            try:
                available_client_id = await asyncio.wait_for(
                    self.client_queue.get(), timeout=50
                )

                async with self.lock:
                    if (
                        available_client_id in self.clients
                        and self.clients[available_client_id].browser_type
                        == browser_type
                        and not self.clients[available_client_id].in_use
                    ):
                        client_info = self.clients[available_client_id]
                        client_info.in_use = True
                        client_info.last_used = time.time()
                        client_info.use_count += 1
                        self.available_clients.discard(available_client_id)

                        pooled_client = PooledPlaywrightClient(
                            client_info.client_id,
                            client_info.browser,
                            client_info.context,
                            client_info.page,
                            client_info.browser_type,
                            self,
                        )

                        print(
                            f"Acquired waiting {browser_type} client: {available_client_id[:8]}"
                        )
                        return pooled_client

            except asyncio.TimeoutError:
                raise RuntimeError("Timeout waiting for available client in pool")

    async def return_client(self, client_id: str):
        """Return a client back to the pool (called internally by PooledPlaywrightClient)"""
        async with self.lock:
            if client_id in self.clients:
                client_info = self.clients[client_id]
                client_info.in_use = False
                client_info.last_used = time.time()
                self.available_clients.add(client_id)

                # Notify waiting tasks
                try:
                    self.client_queue.put_nowait(client_id)
                except asyncio.QueueFull:
                    pass

                print(
                    f"Returned {client_info.browser_type} client to pool: {client_id[:8]}"
                )

    @asynccontextmanager
    async def get_client_context(self, browser_type: str = "chromium", **options):
        """Context manager for automatic client acquisition and return"""
        client = await self.get_client(browser_type, **options)
        try:
            yield client
        finally:
            await client.return_to_pool()

    async def _cleanup_loop(self):
        """Cleanup idle clients periodically"""
        while self.is_initialized:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_idle_clients()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in cleanup loop: {e}")

    async def _cleanup_idle_clients(self):
        """Remove clients that have been idle for too long"""
        current_time = time.time()
        clients_to_remove = []

        async with self.lock:
            for client_id, client_info in self.clients.items():
                if (
                    not client_info.in_use
                    and current_time - client_info.last_used > self.max_idle_time
                ):
                    clients_to_remove.append(client_id)

        for client_id in clients_to_remove:
            await self._remove_client(client_id)

    async def _remove_client(self, client_id: str):
        """Remove and close a specific client"""
        async with self.lock:
            if client_id in self.clients:
                client_info = self.clients[client_id]
                if not client_info.in_use:
                    try:
                        await client_info.page.close()
                        await client_info.context.close()
                        await client_info.browser.close()
                        del self.clients[client_id]
                        self.available_clients.discard(client_id)
                        print(
                            f"Removed idle {client_info.browser_type} client: {client_id[:8]}"
                        )
                    except Exception as e:
                        print(f"Error removing client {client_id[:8]}: {e}")

    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get current pool statistics"""
        async with self.lock:
            total_clients = len(self.clients)
            in_use = sum(1 for c in self.clients.values() if c.in_use)
            available = len(self.available_clients)

            browser_types = {}
            for client_info in self.clients.values():
                browser_types[client_info.browser_type] = (
                    browser_types.get(client_info.browser_type, 0) + 1
                )

            return {
                "total_clients": total_clients,
                "max_clients": self.max_clients,
                "in_use": in_use,
                "available": available,
                "browser_types": browser_types,
                "utilization": f"{(total_clients / self.max_clients) * 100:.1f}%",
            }

    async def close_all(self):
        """Close all clients and cleanup"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        for client_id in list(self.clients.keys()):
            await self._remove_client(client_id)

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        self.is_initialized = False
        print("PlaywrightPool closed successfully")


# Singleton instance
_playwright_pool: Optional[PlaywrightPool] = None


def get_pool(max_clients: int = 5, max_idle_time: int = 300) -> PlaywrightPool:
    """Get singleton PlaywrightPool instance"""
    global _playwright_pool
    if _playwright_pool is None:
        _playwright_pool = PlaywrightPool(max_clients, max_idle_time)
    return _playwright_pool
