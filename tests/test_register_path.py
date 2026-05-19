"""Tests for the local-mode register-by-path endpoint and local_mode capability flag."""

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pypsa_app.backend.settings as settings_module
from pypsa_app.backend.api.routes import networks_local as networks_local_route
from pypsa_app.backend.api.routes import version as version_route

REGISTER_URL = "/api/v1/networks/register-path"


def _register(client: TestClient, path: str | Path):
    return client.post(REGISTER_URL, json={"absolute_path": str(path)})


def _data_dir_nc_files() -> list[Path]:
    networks_dir = settings_module.settings.networks_path
    if not networks_dir.exists():
        return []
    return list(networks_dir.rglob("*.nc"))


@pytest.fixture
def client(app_factory) -> TestClient:
    app = app_factory(
        (networks_local_route.router, "/api/v1/networks"),
        (version_route.router, "/api/v1/version"),
        local_mode=True,
    )
    with TestClient(app) as c:
        yield c


def test_register_path_happy(client: TestClient, nc_file: Path) -> None:
    r = _register(client, nc_file)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["is_external"] is True
    assert data["file_path"] == str(nc_file.resolve())
    assert data["filename"] == nc_file.name
    # Zero-copy: no .nc file should land in data_dir/networks.
    assert _data_dir_nc_files() == []


def test_register_path_idempotent(client: TestClient, nc_file: Path) -> None:
    r1 = _register(client, nc_file)
    r2 = _register(client, nc_file)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.parametrize(
    "case",
    ["empty", "relative", "missing", "non_nc"],
)
def test_register_path_rejects_invalid(
    client: TestClient, tmp_path: Path, case: str
) -> None:
    if case == "empty":
        path = ""
    elif case == "relative":
        path = "relative/path.nc"
    elif case == "missing":
        path = tmp_path / "does_not_exist.nc"
    else:
        bogus = tmp_path / "not_a_network.txt"
        bogus.write_text("x")
        path = bogus
    assert _register(client, path).status_code == 400


@pytest.mark.parametrize("flag", [True, False])
def test_version_exposes_local_mode_flag(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, flag: bool
) -> None:
    monkeypatch.setattr(settings_module.settings, "local_mode", flag)
    r = client.get("/api/v1/version/")
    assert r.status_code == 200
    assert r.json()["local_mode"] is flag


@pytest.mark.parametrize("local_mode", [True, False])
def test_main_app_gates_import_routes_on_local_mode(
    monkeypatch: pytest.MonkeyPatch, local_mode: bool
) -> None:
    """Reload main.py with local_mode flipped; check which import routes are mounted."""
    monkeypatch.setattr(settings_module.settings, "local_mode", local_mode)
    from pypsa_app.backend import main as main_module

    importlib.reload(main_module)
    routes = {
        (m, r.path) for r in main_module.app.routes for m in getattr(r, "methods", ())
    }
    upload = ("POST", "/api/v1/networks/")
    from_url = ("POST", "/api/v1/networks/from-url")
    register = ("POST", "/api/v1/networks/register-path")
    if local_mode:
        assert upload not in routes
        assert from_url not in routes
        assert register in routes
    else:
        assert upload in routes
        assert from_url in routes
        assert register not in routes
