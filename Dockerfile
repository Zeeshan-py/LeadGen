# LeadForge production image.
#
# Builds the static Next.js frontend, installs the FastAPI backend, copies the
# frontend export into the runtime image, and starts through backend/entrypoint.sh.
FROM node:22-alpine AS frontend-builder

WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build \
    && test -f /build/out/ai-sdr/index.html \
    && test -f /build/out/ai-sdr/call/index.html

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    FRONTEND_STATIC_DIR=/app/frontend

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY backend ./
COPY --from=frontend-builder /build/out ./frontend

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
