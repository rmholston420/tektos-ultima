# ──────────────────────────────────────────────────────────────────────────────
# Tektos Dockerfile — Production build
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Frontend (Node.js) ─────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /app

# Install deps
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Build frontend
COPY frontend/ .
RUN npm run build

# ── Stage 2: Backend (Python) ───────────────────────────────────────────────
FROM python:3.12-slim AS backend

# Metadata labels
LABEL org.opencontainers.image.title="tektos-backend" \
      org.opencontainers.image.description="Tektos AI agent backend" \
      org.opencontainers.image.version="1.0" \
      org.opencontainers.image.source="https://github.com/nousresearch/tektos-ultima-v1"

# Create non-root user for security
RUN groupadd --gid 1000 tektos \
    && useradd --uid 1000 --gid tektos --create-home tektos

# Install system deps (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python project
COPY pyproject.toml .
COPY src/tektos/ src/tektos/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Copy frontend build from Stage 1
COPY --from=frontend-builder /app/.next .next
COPY --from=frontend-builder /app/public ./public

# Create data directory with proper permissions
RUN mkdir -p /data && chown -R tektos:tektos /data

# Switch to non-root user
USER tektos

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8020/api/sessions || exit 1

# Expose ports (backend API + debugger)
EXPOSE 8020
EXPOSE 5555

# Environment defaults
ENV DB_PATH=/data/events.db \
    BACKEND_URL=http://localhost:8020 \
    PYTHONUNBUFFERED=1

# Run
CMD ["python", "-m", "tektos.main"]
