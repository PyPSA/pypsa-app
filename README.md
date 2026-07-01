# PyPSA App
Self-hosted web application for analyzing and visualizing PyPSA networks, with modular
architecture designed to extend into workflow execution, network editing, optimization,
and custom integrations.

## Running the App

Both modes require the frontend to be running on the host. See [Frontend](#frontend) below.

### Containerized mode (supported)

Runs the full backend stack in Docker (Postgres, Redis, Prefect worker, and the Python API).
This is the supported way to verify the app works end to end.

**Requirements:** [Docker](https://docs.docker.com/get-docker/) with Compose

```bash
docker compose -f compose/compose.yaml --env-file compose/.env.local up --build
```

API docs available at [`http://localhost:8000/docs`](http://localhost:8000/docs).

### Dev mode (for developer convenience)

Runs infrastructure services in Docker while the API runs on the host, enabling hot-reload
and faster iteration during development.

**Requirements:**
- Python ≥ 3.13 + [uv](https://docs.astral.sh/uv/)
- [Docker](https://docs.docker.com/get-docker/) with Compose

**1. Start Postgres, Redis, and the Prefect worker**

```bash
docker compose -f compose/compose.services.yaml --env-file compose/.env.local up
```

**2. Run the backend API**

```bash
uv run --extra full --env-file compose/.env.local pypsa-app serve --reload
```

API docs available at [`http://localhost:8000/docs`](http://localhost:8000/docs).

### Frontend

Currently non-existent.

## Running Tests

**Requirements:** Python ≥ 3.13 + [uv](https://docs.astral.sh/uv/)

Install dev dependencies (first time only):

```bash
uv sync --extra dev
```

Run the test suite:

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov
```

Migration tests also run against Postgres if `TEST_POSTGRES_URL` is set:

```bash
TEST_POSTGRES_URL=postgresql://user:pass@localhost/testdb uv run pytest
```

## License

The PyPSA App is licensed under the `AGPL-3.0` license.
