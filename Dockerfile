# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim AS backend
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python project
COPY pyproject.toml .
COPY src/tektos/ src/tektos/
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Copy frontend build
COPY --from=frontend-builder /app/.next .next
COPY --from=frontend-builder /app/public ./public

# Create data dir
RUN mkdir -p /data

ENV DB_PATH=/data/events.db
ENV BACKEND_URL=http://localhost:8020
EXPOSE 8020
EXPOSE 5555

CMD ["python", "-m", "tektos.main"]
