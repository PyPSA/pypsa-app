# Stage 1: Builder stage
FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    libhdf5-dev \
    libnetcdf-dev \
    && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml uv.lock MANIFEST.in ./
COPY src/ src/
COPY .git/ .git/

# Sync dependencies with uv
RUN uv sync --frozen --extra full --no-dev

# Stage 2: Runtime stage (pypsa-app backend)
FROM python:3.13-slim AS backend

WORKDIR /app

# Install minimal runtime libraries
RUN apt-get update && apt-get install -y \
    libhdf5-310 \
    libnetcdf22 \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder stage
COPY --from=builder /root/.local/bin/uv /usr/local/bin/uv
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

COPY pyproject.toml uv.lock MANIFEST.in ./

# Create non-root user for running the application
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser

RUN mkdir -p /data/networks && \
    chown -R appuser:appuser /app /data

USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["pypsa-app", "serve"]


# Stage 3: Build Svelte frontend (main app)
FROM node:22-alpine AS app-builder

WORKDIR /frontend

# Use Docker-compatible build paths
ENV DOCKER_BUILD=true

COPY frontend/app/package*.json ./
COPY frontend/app/ ./

RUN npm ci && \
    npm run build && \
    npm cache clean --force


# Stage 4: Build map page with Kepler.gl and React (/network/map)
FROM node:22-alpine AS map-builder

WORKDIR /map

# Use Docker-compatible build paths
ENV DOCKER_BUILD=true

COPY frontend/map/package*.json ./
COPY frontend/map/ ./

RUN npm ci && \
    npm run build && \
    npm cache clean --force


# Stage 5: Full stack (adds built frontends to backend base)
FROM backend AS full

COPY --from=app-builder /frontend/build/ src/pypsa_app/backend/static/app/
COPY --from=map-builder /map/dist/ src/pypsa_app/backend/static/map/

# Copy package.json files for version detection
COPY --from=app-builder /frontend/package.json frontend/app/package.json
COPY --from=map-builder /map/package.json frontend/map/package.json
