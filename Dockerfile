# syntax=docker/dockerfile:1
#
# Multi-stage build for the Bus ETA product:
#  - Stage 1 (builder): install backend deps + build the web static bundle.
#  - Stage 2 (runtime): run the FastAPI API on :8000 and serve the web PWA
#    from :4173 via Nginx.

# ----------------------------- Builder -----------------------------
FROM python:3.13-slim AS builder

# Build deps for any native Python packages + Node for the web bundle.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential curl wget gnupg ca-certificates \
        nginx \
    && rm -rf /var/lib/apt/lists/*

# --- Python backend deps ---
WORKDIR /app/transportation-api
COPY transportation-api/requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# --- Web static bundle (Vite build) ---
FROM node:20-slim AS web-builder
WORKDIR /web
COPY web-app/package.json web-app/package-lock.json* ./
RUN npm install
COPY web-app/ ./
# VITE_API_TARGET points the dev proxy; for the static build we keep relative
# /api and /v1 paths so it works same-origin behind Nginx (no CORS).
RUN npm run build

# ----------------------------- Runtime -----------------------------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    USE_MOCK_DATA=0

# Nginx serves the web PWA + proxies /api and /v1 to the API.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx curl \
    && rm -rf /var/lib/apt/lists/*

# Backend code + venv
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app/transportation-api
COPY transportation-api/ .
# Provide a sane default .env (values come from .env.example).
RUN cp -n .env.example .env || true

# Web static bundle
COPY --from=web-builder /web/dist /var/www/buseta

# Nginx config: web on :4173, API upstream on :8000
RUN rm -f /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/conf.d/buseta.conf

# Entrypoint starts the API (uvicorn) and Nginx together.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000 4173
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
