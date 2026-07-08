# Backend-only runtime image for LeadForge FastAPI.
#
# Used when deploying the API separately from the frontend static export.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY backend ./

RUN chmod +x /app/entrypoint.sh \
    && groupadd --system leadgen \
    && useradd --system --gid leadgen --home-dir /app leadgen \
    && mkdir -p /app/storage/screenshots \
    && chown -R leadgen:leadgen /app

USER leadgen

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:${PORT:-8000}/health/ready || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
