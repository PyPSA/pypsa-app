"""Tests for slowapi-backed per-route rate limiting."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

import pypsa_app.backend.ratelimit as ratelimit_module
import pypsa_app.backend.settings as settings_module
from pypsa_app.backend.ratelimit import (
    get_client_ip,
    rate_limit_exceeded_handler,
    rate_limit_key,
)
from pypsa_app.backend.settings import Settings

_SERVER_ENV = {
    "LOCAL_MODE": "false",
    "REDIS_URL": "redis://localhost:6379/0",
    "DATABASE_URL": "postgresql://x/y",
    "SESSION_SECRET_KEY": "x" * 40,
    "AUTH_PASSWORD_ENABLED": "true",
    "DEMO_MODE": "true",
}


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        (_SERVER_ENV, True),
        ({"LOCAL_MODE": "true"}, False),
        ({**_SERVER_ENV, "RATELIMIT_ENABLED": "false"}, False),
    ],
    ids=["server", "local", "override"],
)
def test_ratelimit_enabled(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: bool
) -> None:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert Settings().ratelimit_enabled is expected


def _fake_request(
    *,
    client_host: str | None = "127.0.0.1",
    cf_ip: str | None = None,
    user: object | None = None,
) -> Request:
    """Build a minimal Request stand-in for get_client_ip / rate_limit_key."""
    headers = {"cf-connecting-ip": cf_ip} if cf_ip else {}
    state = SimpleNamespace(user=user)
    client = SimpleNamespace(host=client_host) if client_host else None
    # Cast to Request for the typechecker; the functions only touch the
    # attributes set here.
    return SimpleNamespace(headers=headers, state=state, client=client)  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("trust_cf", "cf_ip", "client_host", "expected"),
    [
        (True, "1.2.3.4", "10.0.0.1", "1.2.3.4"),
        (True, None, "10.0.0.1", "10.0.0.1"),
        (False, "1.2.3.4", "10.0.0.1", "10.0.0.1"),
        (False, None, None, "unknown"),
    ],
    ids=["cf-trusted", "cf-trusted-missing", "cf-untrusted", "no-client"],
)
def test_get_client_ip(
    monkeypatch: pytest.MonkeyPatch,
    trust_cf: bool,
    cf_ip: str | None,
    client_host: str | None,
    expected: str,
) -> None:
    monkeypatch.setattr(settings_module.settings, "trust_cloudflare_ip", trust_cf)
    req = _fake_request(client_host=client_host, cf_ip=cf_ip)
    assert get_client_ip(req) == expected


_ALICE = SimpleNamespace(id="user-uuid", username="alice")
_DEMO = SimpleNamespace(id="demo-uuid", username="demo")


@pytest.mark.parametrize(
    ("user", "cf_ip", "client_host", "trust_cf", "expected"),
    [
        (_ALICE, None, "10.0.0.1", False, "user:user-uuid"),
        # Shared `demo` account must not get a per-user bucket — bucket by IP.
        (_DEMO, "1.1.1.1", None, True, "ip:1.1.1.1"),
        (None, None, "10.0.0.9", False, "ip:10.0.0.9"),
    ],
    ids=["user", "demo", "anon"],
)
def test_rate_limit_key(
    monkeypatch: pytest.MonkeyPatch,
    user: object | None,
    cf_ip: str | None,
    client_host: str | None,
    trust_cf: bool,
    expected: str,
) -> None:
    monkeypatch.setattr(settings_module.settings, "trust_cloudflare_ip", trust_cf)
    req = _fake_request(user=user, client_host=client_host, cf_ip=cf_ip)
    assert rate_limit_key(req) == expected


def _make_rl_app(monkeypatch: pytest.MonkeyPatch, limit: str) -> FastAPI:
    """Minimal FastAPI app exercising slowapi end-to-end with a fresh Limiter."""
    monkeypatch.setattr(settings_module.settings, "trust_cloudflare_ip", True)
    test_limiter = Limiter(
        key_func=rate_limit_key,
        storage_uri="memory://",
        enabled=True,
        swallow_errors=True,
        headers_enabled=True,
        strategy="moving-window",
    )
    # Reuse the production exception handler — it pulls the limiter off
    # `request.app.state.limiter`, so the test app must register the test one.
    monkeypatch.setattr(ratelimit_module, "limiter", test_limiter)

    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.middleware("http")
    async def _attach_user(request, call_next):  # noqa: ANN001
        request.state.user = None
        return await call_next(request)

    @app.post("/route")
    @test_limiter.limit(limit)
    async def route(request: Request) -> JSONResponse:  # noqa: ARG001
        # Return a Response (not a dict) so slowapi can inject rate-limit
        # headers without erroring.
        return JSONResponse({"ok": True})

    return app


def test_429_threshold_and_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """N requests under limit pass, N+1th returns 429 with rate-limit headers."""
    limit = 5
    app = _make_rl_app(monkeypatch, f"{limit}/minute")
    with TestClient(app) as client:
        headers = {"CF-Connecting-IP": "10.0.0.1"}
        responses = [
            client.post("/route", headers=headers) for _ in range(limit + 1)
        ]
    codes = [r.status_code for r in responses]
    assert codes == [200] * limit + [429], codes
    last = responses[-1]
    assert last.json()["detail"].startswith("Too many requests.")
    assert "retry-after" in {h.lower() for h in last.headers}
    assert any(h.lower().startswith("x-ratelimit-") for h in last.headers)


def test_per_ip_isolation_via_cf_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Different CF-Connecting-IP values are separate buckets."""
    app = _make_rl_app(monkeypatch, "5/minute")
    with TestClient(app) as client:
        codes_a = [
            client.post(
                "/route", headers={"CF-Connecting-IP": "10.0.0.3"}
            ).status_code
            for _ in range(6)
        ]
        # Fresh IP, fresh bucket.
        code_b = client.post(
            "/route", headers={"CF-Connecting-IP": "10.0.0.4"}
        ).status_code
    assert codes_a == [200] * 5 + [429], codes_a
    assert code_b == 200


def test_expensive_routes_have_decorator() -> None:
    """Plots and statistics routes are registered with the expensive tier."""
    # Importing the route modules registers the decorators on the shared limiter.
    from pypsa_app.backend.api.routes import plots, statistics  # noqa: F401

    # The expensive tier default is "60/minute;600/hour" — two limits per route.
    assert Settings().ratelimit_expensive == "60/minute;600/hour"

    expected = {
        "pypsa_app.backend.api.routes.plots.generate_plot",
        "pypsa_app.backend.api.routes.plots.generate_explore",
        "pypsa_app.backend.api.routes.statistics.get_statistics",
    }
    registered = set(ratelimit_module.limiter._route_limits)
    assert expected <= registered, expected - registered

    n_expected = len(settings_module.settings.ratelimit_expensive.split(";"))
    for qualname in expected:
        limits = ratelimit_module.limiter._route_limits[qualname]
        assert len(limits) == n_expected, (qualname, [str(li.limit) for li in limits])
