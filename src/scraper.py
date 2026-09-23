"""
scraper.py
----------
Core browser-automation logic built on async Playwright.

Responsibilities:
  - Launch/close the browser cleanly (as an async context manager)
  - Navigate to each product page with proper waits
  - Extract price + stock status text
  - Take a screenshot of every check (evidence / audit trail)
  - Convert raw page text into a validated (price, currency) pair
  - Never let one product's failure crash the whole run
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)

# Matches things like "£51.77", "$19.99", "19,99 EUR" -> captures symbol/code + numeric amount
_PRICE_PATTERN = re.compile(r"([£$€]|[A-Z]{3})?\s?([\d.,]+)")


@dataclass
class Product:
    name: str
    url: str
    price_selector: str
    stock_selector: Optional[str] = None


@dataclass
class ScrapeResult:
    product: Product
    price: Optional[float]
    currency: str
    in_stock: Optional[bool]
    screenshot_path: Optional[str]
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


def parse_price(raw_text: str) -> tuple[Optional[float], str]:
    """
    Parse a raw price string like '£51.77' into (51.77, 'GBP-ish symbol kept as-is').
    Returns (None, "") if no numeric price could be found.
    """
    if not raw_text:
        return None, ""

    match = _PRICE_PATTERN.search(raw_text.strip())
    if not match:
        return None, ""

    symbol, amount_str = match.groups()
    amount_str = amount_str.replace(",", "")
    try:
        amount = float(amount_str)
    except ValueError:
        return None, ""

    return amount, (symbol or "").strip()


def parse_stock(raw_text: str) -> Optional[bool]:
    """Best-effort interpretation of an availability string."""
    if not raw_text:
        return None
    lowered = raw_text.lower()
    if "out of stock" in lowered or "unavailable" in lowered:
        return False
    if "in stock" in lowered or "available" in lowered:
        return True
    return None


class PriceMonitorScraper:
    """
    Async context manager wrapping a Playwright browser session.

    Usage:
        async with PriceMonitorScraper() as scraper:
            result = await scraper.check_product(product)
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> "PriceMonitorScraper":
        self._playwright = await async_playwright().start()
        browser_launcher = getattr(self._playwright, settings.browser_type)
        logger.info(
            "Launching %s browser (headless=%s)...", settings.browser_type, settings.headless
        )
        self._browser = await browser_launcher.launch(headless=settings.headless)
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 PriceMonitorBot/1.0"
            )
        )
        self._context.set_default_navigation_timeout(settings.navigation_timeout_ms)
        self._context.set_default_timeout(settings.default_wait_ms)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Close resources in reverse order of creation, defensively.
        try:
            if self._context:
                await self._context.close()
        finally:
            try:
                if self._browser:
                    await self._browser.close()
            finally:
                if self._playwright:
                    await self._playwright.stop()
        logger.info("Browser resources closed.")

    async def _new_page(self) -> Page:
        assert self._context is not None, "Scraper must be used inside 'async with'"
        return await self._context.new_page()

    async def _take_screenshot(self, page: Page, product_name: str) -> Optional[str]:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", product_name).strip("_").lower()
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{stamp}.png"
        path = Path(settings.screenshots_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            await page.screenshot(path=str(path), full_page=True)
            logger.debug("Saved screenshot: %s", path)
            return str(path)
        except Exception as exc:  # pragma: no cover - screenshot failures shouldn't crash a run
            logger.warning("Failed to capture screenshot for '%s': %s", product_name, exc)
            return None

    async def check_product(self, product: Product) -> ScrapeResult:
        """
        Navigate to a single product page, extract price/stock, and screenshot it.
        Any failure is caught and returned inside ScrapeResult.error rather than raised,
        so a single bad URL never aborts the whole monitoring run.
        """
        page = await self._new_page()
        screenshot_path: Optional[str] = None
        try:
            logger.info("Checking '%s' -> %s", product.name, product.url)
            await page.goto(product.url, wait_until="domcontentloaded")

            # Proper explicit wait: wait for the specific price element to be visible
            # rather than a blind sleep.
            await page.wait_for_selector(product.price_selector, state="visible")

            price_text = await page.locator(product.price_selector).first.inner_text()
            price, currency = parse_price(price_text)

            in_stock: Optional[bool] = None
            if product.stock_selector:
                try:
                    stock_locator = page.locator(product.stock_selector).first
                    await stock_locator.wait_for(state="visible", timeout=settings.default_wait_ms)
                    stock_text = await stock_locator.inner_text()
                    in_stock = parse_stock(stock_text)
                except PlaywrightTimeoutError:
                    logger.debug("Stock selector not found for '%s'; leaving stock status unknown.", product.name)

            screenshot_path = await self._take_screenshot(page, product.name)

            if price is None:
                raise ValueError(f"Could not parse a price from text: '{price_text}'")

            logger.info("'%s' -> price=%s%.2f, in_stock=%s", product.name, currency, price, in_stock)
            return ScrapeResult(
                product=product,
                price=price,
                currency=currency,
                in_stock=in_stock,
                screenshot_path=screenshot_path,
            )

        except PlaywrightTimeoutError as exc:
            logger.error("Timeout while checking '%s': %s", product.name, exc)
            screenshot_path = screenshot_path or await self._take_screenshot(page, f"{product.name}_error")
            return ScrapeResult(
                product=product, price=None, currency="", in_stock=None,
                screenshot_path=screenshot_path, error=f"Timeout: {exc}",
            )
        except Exception as exc:  # noqa: BLE001 - top-level guard, deliberately broad
            logger.error("Error while checking '%s': %s", product.name, exc)
            screenshot_path = screenshot_path or await self._take_screenshot(page, f"{product.name}_error")
            return ScrapeResult(
                product=product, price=None, currency="", in_stock=None,
                screenshot_path=screenshot_path, error=str(exc),
            )
        finally:
            await page.close()

    async def check_products(self, products: list[Product]) -> list[ScrapeResult]:
        """Sequentially check a list of products, isolating failures per-product."""
        results: list[ScrapeResult] = []
        for product in products:
            result = await self.check_product(product)
            results.append(result)
        return results
