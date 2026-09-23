"""
test_scraper.py
----------------
Unit tests for pure-logic helpers (price/stock text parsing). These don't
require a browser or network access, so they run fast in CI.

For end-to-end tests that actually launch a browser, see test_integration.py
(marked slow / requires network).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scraper import parse_price, parse_stock  # noqa: E402


class TestParsePrice:
    def test_parses_pound_price(self):
        price, currency = parse_price("£51.77")
        assert price == 51.77
        assert currency == "£"

    def test_parses_dollar_price(self):
        price, currency = parse_price("$19.99")
        assert price == 19.99
        assert currency == "$"

    def test_parses_price_with_thousands_separator(self):
        price, _ = parse_price("$1,299.00")
        assert price == 1299.00

    def test_parses_plain_number(self):
        price, currency = parse_price("42.50")
        assert price == 42.50
        assert currency == ""

    def test_returns_none_for_empty_string(self):
        price, currency = parse_price("")
        assert price is None
        assert currency == ""

    def test_returns_none_for_non_numeric_text(self):
        price, currency = parse_price("Price unavailable")
        assert price is None


class TestParseStock:
    def test_detects_in_stock(self):
        assert parse_stock("In stock (22 available)") is True

    def test_detects_out_of_stock(self):
        assert parse_stock("Out of stock") is False

    def test_detects_available_keyword(self):
        assert parse_stock("Available for order") is True

    def test_returns_none_for_unclear_text(self):
        assert parse_stock("Ships in 3-5 days") is None

    def test_returns_none_for_empty_string(self):
        assert parse_stock("") is None
