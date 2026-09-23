"""
config.py
---------
Centralized, validated configuration loading.

All runtime settings come from environment variables (loaded from a local
.env file via python-dotenv). Nothing sensitive is hardcoded in source code.
Import `settings` from this module anywhere config values are needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file in the project root, if present.
# In CI/CD or containers, real environment variables take precedence.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass
class Settings:
    # Browser
    headless: bool = field(default_factory=lambda: _get_bool("HEADLESS", True))
    browser_type: str = field(default_factory=lambda: os.getenv("BROWSER_TYPE", "chromium"))
    navigation_timeout_ms: int = field(default_factory=lambda: _get_int("NAVIGATION_TIMEOUT_MS", 30000))
    default_wait_ms: int = field(default_factory=lambda: _get_int("DEFAULT_WAIT_MS", 5000))

    # Monitoring
    products_file: str = field(default_factory=lambda: os.getenv("PRODUCTS_FILE", "config/products.json"))
    check_interval_minutes: int = field(default_factory=lambda: _get_int("CHECK_INTERVAL_MINUTES", 60))
    price_drop_threshold_percent: float = field(
        default_factory=lambda: _get_float("PRICE_DROP_THRESHOLD_PERCENT", 5.0)
    )

    # Storage
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "data"))
    screenshots_dir: str = field(default_factory=lambda: os.getenv("SCREENSHOTS_DIR", "screenshots"))
    logs_dir: str = field(default_factory=lambda: os.getenv("LOGS_DIR", "logs"))
    csv_export_file: str = field(default_factory=lambda: os.getenv("CSV_EXPORT_FILE", "data/price_history.csv"))

    # Email (optional)
    enable_email_alerts: bool = field(default_factory=lambda: _get_bool("ENABLE_EMAIL_ALERTS", False))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: _get_int("SMTP_PORT", 587))
    smtp_username: str = field(default_factory=lambda: os.getenv("SMTP_USERNAME", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    alert_email_from: str = field(default_factory=lambda: os.getenv("ALERT_EMAIL_FROM", ""))
    alert_email_to: str = field(default_factory=lambda: os.getenv("ALERT_EMAIL_TO", ""))

    def validate(self) -> list[str]:
        """Return a list of human-readable configuration problems, if any."""
        problems: list[str] = []
        if self.browser_type not in {"chromium", "firefox", "webkit"}:
            problems.append(f"BROWSER_TYPE must be one of chromium/firefox/webkit, got '{self.browser_type}'")
        if self.enable_email_alerts:
            missing = [
                var
                for var, val in [
                    ("SMTP_HOST", self.smtp_host),
                    ("SMTP_USERNAME", self.smtp_username),
                    ("SMTP_PASSWORD", self.smtp_password),
                    ("ALERT_EMAIL_FROM", self.alert_email_from),
                    ("ALERT_EMAIL_TO", self.alert_email_to),
                ]
                if not val
            ]
            if missing:
                problems.append(f"ENABLE_EMAIL_ALERTS is true but missing: {', '.join(missing)}")
        return problems

    def ensure_directories(self) -> None:
        """Create output directories if they don't already exist."""
        for d in (self.data_dir, self.screenshots_dir, self.logs_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()
