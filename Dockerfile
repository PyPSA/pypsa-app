# syntax=docker/dockerfile:1

# Stage 1: Builder stage
FROM python:3.14-slim@sha256:d7a925f9eb9639a93e455b9f12c167569358818c0f62b51b88edbc8fcf34c421 AS builder

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
FROM python:3.14-slim@sha256:d7a925f9eb9639a93e455b9f12c167569358818c0f62b51b88edbc8fcf34c421 AS backend

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
