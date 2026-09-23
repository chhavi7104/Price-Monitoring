"""
main.py
-------
CLI entry point for the price monitor.

Examples
--------
Run a single check against all configured products:
    python -m src.main run

Run a single check and export results to CSV:
    python -m src.main run --export csv

Run continuously, checking every CHECK_INTERVAL_MINUTES:
    python -m src.main run --loop

Export existing history without scraping:
    python -m src.main export --format excel
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from src.config import settings
from src.logger import get_logger
from src.notifier import send_price_drop_alert
from src.scraper import PriceMonitorScraper, Product, ScrapeResult
from src.storage import export_csv, export_excel, get_last_price, make_record, append_record

logger = get_logger(__name__)


def load_products(path: str | None = None) -> list[Product]:
    """Load the list of products to monitor from a JSON config file."""
    products_path = Path(path or settings.products_file)
    if not products_path.exists():
        raise FileNotFoundError(
            f"Products config not found at '{products_path}'. "
            "Create it (see config/products.json for the expected format) "
            "or set PRODUCTS_FILE in your .env."
        )
    with products_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    products = [
        Product(
            name=item["name"],
            url=item["url"],
            price_selector=item["price_selector"],
            stock_selector=item.get("stock_selector"),
        )
        for item in raw
    ]
    if not products:
        raise ValueError(f"Products config at '{products_path}' is empty.")
    return products


def _evaluate_price_drop(result: ScrapeResult) -> None:
    """Compare against the last recorded price and fire an alert if it dropped enough."""
    if result.price is None:
        return
    previous_price = get_last_price(result.product.name)
    if previous_price is None or previous_price <= 0:
        return

    drop_percent = ((previous_price - result.price) / previous_price) * 100
    if drop_percent >= settings.price_drop_threshold_percent:
        logger.info(
            "Price drop detected for '%s': %.2f -> %.2f (-%.1f%%)",
            result.product.name, previous_price, result.price, drop_percent,
        )
        send_price_drop_alert(
            product_name=result.product.name,
            old_price=previous_price,
            new_price=result.price,
            url=result.product.url,
        )


async def run_once(products: list[Product]) -> list[ScrapeResult]:
    """Run a single full check across all products and persist results."""
    async with PriceMonitorScraper() as scraper:
        results = await scraper.check_products(products)

    for result in results:
        _evaluate_price_drop(result)
        record = make_record(
            product_name=result.product.name,
            url=result.product.url,
            price=result.price,
            currency=result.currency,
            in_stock=result.in_stock,
            screenshot_path=result.screenshot_path,
            error=result.error,
        )
        append_record(record)

    succeeded = sum(1 for r in results if r.success)
    logger.info("Run complete: %d/%d products checked successfully.", succeeded, len(results))
    return results


def _print_summary(results: list[ScrapeResult]) -> None:
    print("\n" + "=" * 60)
    print(f"{'PRODUCT':<30}{'PRICE':<12}{'STOCK':<10}{'STATUS'}")
    print("-" * 60)
    for r in results:
        price_str = f"{r.currency}{r.price:.2f}" if r.price is not None else "N/A"
        stock_str = {True: "In stock", False: "Out", None: "Unknown"}[r.in_stock]
        status = "OK" if r.success else f"FAILED ({r.error})"
        print(f"{r.product.name[:28]:<30}{price_str:<12}{stock_str:<10}{status}")
    print("=" * 60 + "\n")


def _run_export(fmt: str) -> None:
    if fmt == "csv":
        path = export_csv()
    elif fmt == "excel":
        path = export_excel()
    else:
        raise ValueError(f"Unknown export format: {fmt}")
    print(f"Exported price history -> {path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="price_monitor",
        description="Playwright-based price monitoring automation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Check configured products for price changes.")
    run_parser.add_argument("--products", type=str, default=None, help="Path to a products JSON config file.")
    run_parser.add_argument("--export", choices=["csv", "excel"], default=None, help="Export history after the run.")
    run_parser.add_argument("--loop", action="store_true", help="Keep running on CHECK_INTERVAL_MINUTES.")

    export_parser = subparsers.add_parser("export", help="Export existing price history without scraping.")
    export_parser.add_argument("--format", choices=["csv", "excel"], default="csv")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    settings.ensure_directories()
    problems = settings.validate()
    if problems:
        for p in problems:
            logger.error("Configuration problem: %s", p)
        return 1

    if args.command == "export":
        _run_export(args.format)
        return 0

    # args.command == "run"
    try:
        products = load_products(args.products)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        logger.error(str(exc))
        return 1

    if args.loop:
        interval_seconds = settings.check_interval_minutes * 60
        logger.info("Starting continuous monitoring every %d minute(s). Press Ctrl+C to stop.",
                    settings.check_interval_minutes)
        try:
            while True:
                results = asyncio.run(run_once(products))
                _print_summary(results)
                if args.export:
                    _run_export(args.export)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user.")
            return 0
    else:
        results = asyncio.run(run_once(products))
        _print_summary(results)
        if args.export:
            _run_export(args.export)

    # Non-zero exit code if every single product failed, useful for CI/alerting.
    if results and all(not r.success for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
