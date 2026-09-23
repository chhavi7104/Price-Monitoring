"""
storage.py
----------
Handles persistence of scraped price data:
  - a running JSON history file (one entry per check, per product)
  - CSV export (mandatory-friendly, no extra deps)
  - Excel export (bonus, via pandas/openpyxl)

Keeping storage concerns separate from scraping logic makes both easier to
test and to swap out later (e.g. for a real database).
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PriceRecord:
    product_name: str
    url: str
    price: Optional[float]
    currency: str
    in_stock: Optional[bool]
    timestamp: str
    screenshot_path: Optional[str] = None
    error: Optional[str] = None


def _history_path() -> Path:
    return Path(settings.data_dir) / "price_history.json"


def load_history() -> list[dict]:
    """Load all previously recorded price checks (empty list if none yet)."""
    path = _history_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read history file (%s); starting fresh.", exc)
        return []


def append_record(record: PriceRecord) -> None:
    """Append a single price record to the JSON history file."""
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    history = load_history()
    history.append(asdict(record))
    with path.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    logger.debug("Recorded price history entry for '%s'.", record.product_name)


def get_last_price(product_name: str) -> Optional[float]:
    """Return the most recent previously-recorded price for a product, if any."""
    history = load_history()
    for entry in reversed(history):
        if entry.get("product_name") == product_name and entry.get("price") is not None:
            return entry["price"]
    return None


def export_csv(destination: Optional[str] = None) -> str:
    """Export the full price history to a CSV file. Returns the file path written."""
    destination = destination or settings.csv_export_file
    dest_path = Path(destination)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    history = load_history()
    fieldnames = ["product_name", "url", "price", "currency", "in_stock", "timestamp", "screenshot_path", "error"]

    with dest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in history:
            writer.writerow({k: entry.get(k, "") for k in fieldnames})

    logger.info("Exported %d records to CSV: %s", len(history), dest_path)
    return str(dest_path)


def export_excel(destination: Optional[str] = None) -> str:
    """Export the full price history to an Excel (.xlsx) file. Bonus feature."""
    import pandas as pd  # local import: keep pandas optional for CSV-only users

    destination = destination or str(Path(settings.data_dir) / "price_history.xlsx")
    dest_path = Path(destination)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    history = load_history()
    df = pd.DataFrame(history)
    df.to_excel(dest_path, index=False, engine="openpyxl")

    logger.info("Exported %d records to Excel: %s", len(history), dest_path)
    return str(dest_path)


def make_record(
    product_name: str,
    url: str,
    price: Optional[float],
    currency: str,
    in_stock: Optional[bool],
    screenshot_path: Optional[str] = None,
    error: Optional[str] = None,
) -> PriceRecord:
    return PriceRecord(
        product_name=product_name,
        url=url,
        price=price,
        currency=currency,
        in_stock=in_stock,
        timestamp=datetime.now(timezone.utc).isoformat(),
        screenshot_path=screenshot_path,
        error=error,
    )
