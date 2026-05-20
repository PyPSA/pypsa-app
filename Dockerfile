# syntax=docker/dockerfile:1

# Stage 1: Builder stage
FROM python:3.13-slim@sha256:d49c1ff87eb98eac346fc250f52925f726eb913c43a92854246dd03c9692ad67 AS builder

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

# Skip setuptools_scm git lookup when .git is unavailable
ARG SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYPSA_APP=
RUN if [ -n "${SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYPSA_APP}" ]; then \
        export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYPSA_APP="${SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYPSA_APP}"; \
    fi && uv sync --frozen --extra full --no-dev

# Stage 2: Runtime stage (pypsa-app backend)
FROM python:3.13-slim@sha256:d49c1ff87eb98eac346fc250f52925f726eb913c43a92854246dd03c9692ad67 AS backend

WORKDIR /app

# Install minimal runtime libraries
RUN apt-get update && apt-get install -y \
    curl \
    gosu \
    tini \
    libhdf5-310 \
    libnetcdf22 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for running the application
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /bin/bash appuser && \
    mkdir -p /data/networks && \
    chown -R appuser:appuser /data

# Copy from builder stage with correct ownership
COPY --from=builder --chown=appuser:appuser /root/.local/bin/uv /usr/local/bin/uv
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src

COPY --chown=appuser:appuser pyproject.toml uv.lock MANIFEST.in alembic.ini ./
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["pypsa-app", "serve"]


# Stage 3: Build Svelte frontend (main app)
FROM node:22-alpine@sha256:968df39aedcea65eeb078fb336ed7191baf48f972b4479711397108be0966920 AS app-builder

WORKDIR /frontend

# Use Docker-compatible build paths
ENV DOCKER_BUILD=true

COPY frontend/app/package*.json ./
COPY frontend/app/ ./

RUN npm ci && \
    npm run build && \
    npm cache clean --force


# Stage 4: Full stack (adds built frontend to backend base)
FROM backend AS full

COPY --from=app-builder --chown=appuser:appuser /frontend/build/ src/pypsa_app/backend/static/app/

# Copy package.json for version detection
COPY --from=app-builder --chown=appuser:appuser /frontend/package.json frontend/app/package.json
