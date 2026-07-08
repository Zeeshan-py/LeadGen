# Frontend-only image for the LeadForge Next.js static export.
#
# Useful when the frontend is hosted separately from the FastAPI backend. The
# app is exported to /out, so this image serves static files instead of running
# the Next.js production server.
FROM node:22-alpine AS deps
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY frontend ./
RUN npm run build \
    && test -f /app/out/ai-sdr/index.html \
    && test -f /app/out/ai-sdr/call/index.html

FROM nginx:1.27-alpine AS runner
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/out /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
