#!/bin/sh
set -eu

attempt=1
until alembic upgrade head; do
  if [ "$attempt" -ge 12 ]; then
    echo "Database migration failed after $attempt attempts." >&2
    exit 1
  fi
  echo "Database is not ready; retrying migration in 5 seconds ($attempt/12)." >&2
  attempt=$((attempt + 1))
  sleep 5
done

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
