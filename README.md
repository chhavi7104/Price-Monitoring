# Price Monitor — Playwright Browser Automation

A production-ready price monitoring bot built with **Python 3** and **Microsoft Playwright**
(async API). It navigates to a configurable list of product pages, extracts price and stock
status, screenshots each check for an audit trail, tracks price history over time, alerts on
price drops, and exports everything to CSV/Excel.

Built for Task 3 — Week 3 Browser Automation project.

---

## Features

| Requirement | Implementation |
|---|---|
| Launch browsers | `async_playwright()` via `PriceMonitorScraper` async context manager (`src/scraper.py`) |
| Navigate pages | `page.goto(url, wait_until="domcontentloaded")` |
| Interact with forms | Locator-based extraction (`page.locator(selector)`); easily extended to fill forms |
| Proper waits | `page.wait_for_selector(..., state="visible")` — no blind `sleep()` calls |
| Validate execution | Every result is typed (`ScrapeResult`), success/failure explicitly tracked |
| Close resources | `__aexit__` closes context → browser → playwright, in order, even on error |
| .env configuration | `python-dotenv` + `src/config.py`, see `.env.example` |
| Logging | Rotating file + console logger (`src/logger.py`), written to `logs/` |
| Exception handling | Per-product try/except — one bad page never kills the whole run |
| Screenshots | Full-page screenshot on every check (success **and** failure) → `screenshots/` |
| README | This file |

### Bonus features included
- **Async Playwright** (not sync) throughout
- **Headless mode** toggle via `.env`
- **CLI** with subcommands and flags (`argparse`)
- **CSV and Excel export** (`src/storage.py`)
- **Docker** support (official Playwright base image, browsers preinstalled)
- **GitHub Actions CI** running the unit test suite on every push
- **Unit tests** (16 tests, pure-logic, no browser/network needed) via `pytest`
- **Email notifications** on price drops (optional, stdlib `smtplib`)

---

## Project Structure

```
price_monitor/
├── .env.example              # Copy to .env and fill in your own values
├── .gitignore
├── Dockerfile
├── requirements.txt
├── README.md
├── config/
│   └── products.json         # List of products to monitor (name, url, CSS selectors)
├── src/
│   ├── config.py             # Env-driven settings, validated at startup
│   ├── logger.py             # Rotating file + console logging
│   ├── scraper.py            # Core async Playwright automation logic
│   ├── storage.py            # JSON history store + CSV/Excel export
│   ├── notifier.py           # Optional email alerts on price drops
│   └── main.py                # CLI entry point (argparse)
├── tests/
│   ├── test_scraper.py       # Unit tests for price/stock text parsing
│   └── test_storage.py       # Unit tests for the persistence layer
├── data/                      # price_history.json / .csv / .xlsx (generated, gitignored)
├── screenshots/                # PNG evidence per check (generated, gitignored)
├── logs/                       # price_monitor.log (generated, gitignored)
└── .github/workflows/ci.yml   # Runs pytest on every push/PR
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd price_monitor
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — at minimum leave the defaults, or adjust `HEADLESS`, `PRICE_DROP_THRESHOLD_PERCENT`,
and the email settings if you want alerts. **Never commit your real `.env` file** — it's already
in `.gitignore`.

### 3. Configure products to track

Edit `config/products.json`. Each entry needs a `name`, `url`, a CSS `price_selector`, and an
optional `stock_selector`. The included example targets
[books.toscrape.com](https://books.toscrape.com), a public sandbox site built specifically for
scraping practice — swap in real product URLs and matching selectors for your own use case.

```json
{
  "name": "A Light in the Attic",
  "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "price_selector": "p.price_color",
  "stock_selector": "p.instock.availability"
}
```

---

## Usage

Run a single check against all configured products:

```bash
python -m src.main run
```

Run a check and export the full history to CSV or Excel afterward:

```bash
python -m src.main run --export csv
python -m src.main run --export excel
```

Run continuously (respecting `CHECK_INTERVAL_MINUTES` from `.env`):

```bash
python -m src.main run --loop
```

Use a different products file:

```bash
python -m src.main run --products config/my_other_products.json
```

Export existing history without scraping again:

```bash
python -m src.main export --format csv
```

Sample console output:

```
============================================================
PRODUCT                       PRICE       STOCK     STATUS
------------------------------------------------------------
A Light in the Attic          £51.77      In stock  OK
Tipping the Velvet            £53.74      In stock  OK
Soumission                    £50.10      In stock  OK
============================================================
```

Exit codes: `0` success, `1` configuration/setup error, `2` every product failed (useful for
CI/cron alerting).

---

## Running with Docker

```bash
docker build -t price-monitor .
docker run --rm --env-file .env -v $(pwd)/data:/app/data -v $(pwd)/screenshots:/app/screenshots price-monitor
```

---

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

16 unit tests cover price-text parsing, stock-status parsing, and the storage layer, using
`tmp_path`/`monkeypatch` fixtures so they never touch real project files or the network. CI runs
these automatically on every push via `.github/workflows/ci.yml`.

---

## How it works (architecture)

1. **`main.py`** parses CLI args, loads `config/products.json` into `Product` objects, and
   orchestrates a run.
2. **`scraper.py`** opens one Playwright browser session (`async with PriceMonitorScraper()`),
   then visits each product page in turn:
   - waits for the price element to actually be visible (not a fixed sleep),
   - extracts and parses the price/currency and stock text,
   - takes a full-page screenshot regardless of success or failure,
   - catches any exception per-product so one broken URL doesn't stop the batch.
3. **`storage.py`** appends every check to a JSON history file, and can export the full history
   to CSV or Excel on demand.
4. **`main.py`** compares each new price against the last recorded price for that product; if it
   dropped by more than `PRICE_DROP_THRESHOLD_PERCENT`, **`notifier.py`** sends an email alert
   (only if `ENABLE_EMAIL_ALERTS=true`).
5. **`logger.py`** writes a running log to both the console and a rotating file under `logs/`.

---

## Notes on the demo target site

`config/products.json` points at `books.toscrape.com`, a purpose-built public scraping sandbox
(not a real store) — the correct kind of target for demonstrating automation without touching a
live commercial site's terms of service. To monitor a real product, just add its URL and the
right CSS selector for its price element to `config/products.json`; no code changes required.

---

## Submission checklist

- [ ] Push this repository to GitHub
- [ ] Confirm `.env` is **not** committed (check `.gitignore`)
- [ ] Record a 2–5 minute demo video showing: `python -m src.main run`, the console summary,
      generated screenshots, `data/price_history.json`/`.csv`, and the log file
- [ ] Write the mandatory LinkedIn post
- [ ] Link the GitHub repo in the submission form
