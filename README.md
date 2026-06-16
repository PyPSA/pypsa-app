# PyPSA App
Self-hosted web application for analyzing and visualizing PyPSA networks, with modular
architecture designed to extend into workflow execution, network editing, optimization,
and custom integrations.

## Development Setup

### Requirements

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Docker](https://docs.docker.com/get-docker/) with Compose
- Node.js 22.x (for the frontend)

### 1. Start Postgres, Redis, and the Celery worker

```bash
docker compose -f compose/compose.services.yaml --env-file compose/.env.local up
```

### 2. Run the backend API

```bash
uv run --extra full --env-file compose/.env.local pypsa-app serve --reload --dev
```

API docs available at [`http://localhost:8000/docs`](http://localhost:8000/docs).

### 3. Run the frontend

```bash
cd frontend/app
npm install
npm run dev
```

App available at [`http://localhost:5173`](http://localhost:5173).

## License

The PyPSA App is licensed under the `AGPL-3.0` license.
