"""Tests para el middleware de logging estructurado."""
import json
import pytest
import structlog
from httpx import AsyncClient
from unittest.mock import patch


# ── Middleware de request logging ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_log_contains_method_and_path(client: AsyncClient):
    """Cada request debe producir un log con method y path."""
    with structlog.testing.capture_logs() as logs:
        await client.get("/health")

    request_logs = [r for r in logs if r.get("event") == "http_request"]
    assert len(request_logs) >= 1
    log = request_logs[0]
    assert log.get("method") == "GET"
    assert log.get("path") == "/health"


@pytest.mark.asyncio
async def test_request_log_contains_status_and_duration(client: AsyncClient):
    """El log de request debe incluir status_code y duration_ms."""
    with structlog.testing.capture_logs() as logs:
        await client.get("/health")

    request_logs = [r for r in logs if r.get("event") == "http_request"]
    assert len(request_logs) >= 1
    log = request_logs[0]
    assert "status_code" in log
    assert "duration_ms" in log
    assert isinstance(log["duration_ms"], float)
    assert log["status_code"] == 200


@pytest.mark.asyncio
async def test_request_log_includes_request_id(client: AsyncClient):
    """Cada request debe tener un request_id único en el log."""
    with structlog.testing.capture_logs() as logs:
        await client.get("/health")
        await client.get("/health")

    request_logs = [r for r in logs if r.get("event") == "http_request"]
    assert len(request_logs) >= 2
    ids = [r.get("request_id") for r in request_logs]
    assert all(ids), "Todos los logs deben tener request_id"
    assert ids[0] != ids[1], "Cada request debe tener un request_id distinto"


@pytest.mark.asyncio
async def test_authenticated_request_log_includes_user_id(
    client: AsyncClient, superadmin_token: str, superadmin_user
):
    """Si el request está autenticado, el log debe incluir user_id."""
    with structlog.testing.capture_logs() as logs:
        await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )

    request_logs = [r for r in logs if r.get("event") == "http_request"]
    assert len(request_logs) >= 1
    log = request_logs[0]
    assert "user_id" in log
    assert log["user_id"] == str(superadmin_user.id)


# ── Logging de eventos de negocio ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_event_is_logged(client: AsyncClient, superadmin_user):
    """Un login exitoso debe producir un log de evento 'user_login'."""
    with structlog.testing.capture_logs() as logs:
        await client.post(
            "/api/v1/auth/login",
            json={"email": superadmin_user.email, "password": "password123"},
        )

    login_events = [r for r in logs if r.get("event") == "user_login"]
    assert len(login_events) >= 1
    event = login_events[0]
    assert event.get("user_id") == str(superadmin_user.id)


@pytest.mark.asyncio
async def test_failed_login_event_is_logged(client: AsyncClient):
    """Un login fallido debe producir un log de evento 'user_login_failed'."""
    with structlog.testing.capture_logs() as logs:
        await client.post(
            "/api/v1/auth/login",
            json={"email": "noexiste@test.com", "password": "wrong"},
        )

    failed_events = [r for r in logs if r.get("event") == "user_login_failed"]
    assert len(failed_events) >= 1


# ── Configuración de structlog y Sentry ───────────────────────────────────────

def test_sentry_init_skipped_when_no_dsn():
    """Si SENTRY_DSN está vacío, Sentry no se inicializa."""
    with patch("sentry_sdk.init") as mock_sentry_init:
        from app.core.logging_config import init_sentry
        init_sentry(dsn="", environment="testing")
        mock_sentry_init.assert_not_called()


def test_sentry_init_called_when_dsn_present():
    """Si SENTRY_DSN está configurado, Sentry debe inicializarse."""
    with patch("sentry_sdk.init") as mock_sentry_init:
        from app.core.logging_config import init_sentry
        init_sentry(dsn="https://fake@sentry.io/123", environment="production")
        mock_sentry_init.assert_called_once()
        call_kwargs = mock_sentry_init.call_args[1]
        assert call_kwargs.get("dsn") == "https://fake@sentry.io/123"
        assert call_kwargs.get("environment") == "production"
