# Playwright's official image ships Python + all browser binaries + OS deps preinstalled,
# which avoids the classic "works on my machine" headless-browser dependency problems.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Directories the app writes to at runtime
RUN mkdir -p data screenshots logs

# Default: run one monitoring pass and export to CSV.
# Override at `docker run` time, e.g.:
#   docker run --env-file .env myimage python -m src.main run --loop
CMD ["python", "-m", "src.main", "run", "--export", "csv"]
