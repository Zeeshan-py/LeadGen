# syntax=docker/dockerfile:1.7

# LeadForge production image.
#
# Build goals:
# - cache Node and Python dependencies independently from application source
# - ship only the FastAPI runtime modules, Alembic migrations, and static frontend
# - keep Playwright screenshot support with the smaller Chromium headless shell

ARG NODE_IMAGE=node:22-alpine
ARG PYTHON_IMAGE=python:3.13-slim

FROM ${NODE_IMAGE} AS frontend-deps
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

FROM ${NODE_IMAGE} AS frontend-builder
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
COPY --from=frontend-deps /build/node_modules ./node_modules
COPY frontend ./
RUN npm run build \
    && test -f /build/out/ai-sdr/index.html \
    && test -f /build/out/ai-sdr/call/index.html

FROM ${PYTHON_IMAGE} AS python-deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_COMPILE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /deps
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY backend/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    && find /opt/venv -type d -name "__pycache__" -prune -exec rm -rf {} +

FROM python-deps AS runtime-base
ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache

FROM runtime-base AS runtime
ENV FRONTEND_STATIC_DIR=/app/frontend \
    PATH="/opt/venv/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system leadgen \
    && useradd --system --gid leadgen --home-dir /app leadgen \
    && mkdir -p /app/storage/screenshots \
    && chown -R leadgen:leadgen /app /ms-playwright

COPY --chown=leadgen:leadgen backend/alembic.ini ./
COPY --chown=leadgen:leadgen --chmod=755 backend/entrypoint.sh ./entrypoint.sh
COPY --chown=leadgen:leadgen backend/app ./app
COPY --chown=leadgen:leadgen backend/ai_sdr ./ai_sdr
COPY --chown=leadgen:leadgen backend/lead_automation ./lead_automation
COPY --chown=leadgen:leadgen backend/migrations ./migrations
COPY --from=frontend-builder --chown=leadgen:leadgen /build/out ./frontend

USER leadgen

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health/ready' % os.getenv('PORT', '8000'), timeout=5).read()"]

ENTRYPOINT ["/app/entrypoint.sh"]
