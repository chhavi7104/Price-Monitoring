"""
notifier.py
-----------
Optional email alerting (bonus feature). Disabled by default; enabled via
ENABLE_EMAIL_ALERTS=true in .env with SMTP credentials supplied there.

Uses only the Python standard library (smtplib/email) so it adds no extra
dependency for users who don't need it.
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


def send_price_drop_alert(product_name: str, old_price: float, new_price: float, url: str) -> bool:
    """
    Send an email alert about a price drop. Returns True on success,
    False if alerts are disabled or sending failed (never raises,
    since a notification failure should not crash the monitoring run).
    """
    if not settings.enable_email_alerts:
        logger.debug("Email alerts disabled; skipping notification for '%s'.", product_name)
        return False

    drop_percent = ((old_price - new_price) / old_price) * 100 if old_price else 0
    subject = f"Price Drop Alert: {product_name} (-{drop_percent:.1f}%)"
    body = (
        f"Good news! A tracked product dropped in price.\n\n"
        f"Product:   {product_name}\n"
        f"Old price: {old_price:.2f}\n"
        f"New price: {new_price:.2f}\n"
        f"Drop:      {drop_percent:.1f}%\n"
        f"URL:       {url}\n"
    )

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.alert_email_from
    message["To"] = settings.alert_email_to

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.alert_email_from, [settings.alert_email_to], message.as_string())
        logger.info("Sent price drop alert email for '%s'.", product_name)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send alert email for '%s': %s", product_name, exc)
        return False
