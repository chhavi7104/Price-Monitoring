"""
test_storage.py
----------------
Unit tests for storage.py. Uses monkeypatching to redirect DATA_DIR to a
temp directory so tests never touch real project data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.storage as storage  # noqa: E402
from src.config import settings  # noqa: E402


def test_make_record_has_expected_fields():
    record = storage.make_record(
        product_name="Test Book",
        url="https://example.com/book",
        price=9.99,
        currency="$",
        in_stock=True,
    )
    assert record.product_name == "Test Book"
    assert record.price == 9.99
    assert record.timestamp  # non-empty ISO timestamp


def test_append_and_load_history(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    record = storage.make_record(
        product_name="Widget",
        url="https://example.com/widget",
        price=12.5,
        currency="$",
        in_stock=True,
    )
    storage.append_record(record)

    history = storage.load_history()
    assert len(history) == 1
    assert history[0]["product_name"] == "Widget"
    assert history[0]["price"] == 12.5


def test_get_last_price_returns_most_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    storage.append_record(storage.make_record("Gadget", "https://x", 10.0, "$", True))
    storage.append_record(storage.make_record("Gadget", "https://x", 8.0, "$", True))

    assert storage.get_last_price("Gadget") == 8.0


def test_get_last_price_returns_none_when_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    assert storage.get_last_price("Never Seen Product") is None


def test_export_csv_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    storage.append_record(storage.make_record("Gadget", "https://x", 10.0, "$", True))

    dest = tmp_path / "out.csv"
    result_path = storage.export_csv(str(dest))

    assert Path(result_path).exists()
    content = Path(result_path).read_text(encoding="utf-8")
    assert "Gadget" in content
