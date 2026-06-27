from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch


def test_calendar_auth_uses_real_callback_route(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "1234567890-test.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)

    resp = client.get("/api/calendar/auth", follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers["location"]
    query = parse_qs(urlparse(location).query)
    assert query["redirect_uri"] == ["http://localhost:8000/api/calendar/callback"]


def test_calendar_auth_without_credentials_is_friendly_html(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    resp = client.get("/api/calendar/auth", follow_redirects=False)

    assert resp.status_code == 500
    assert "text/html" in resp.headers["content-type"]
    assert "Google Calendar credentials missing" in resp.text


def test_calendar_auth_with_placeholder_credentials_is_friendly_html(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "your_google_client_id_here")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "your_google_client_secret_here")

    resp = client.get("/api/calendar/auth", follow_redirects=False)

    assert resp.status_code == 500
    assert "text/html" in resp.headers["content-type"]
    assert "Google Calendar credentials missing" in resp.text


def test_calendar_callback_without_code_is_friendly_html(client):
    resp = client.get("/api/calendar/callback")

    assert resp.status_code == 400
    assert "text/html" in resp.headers["content-type"]
    assert "Calendar connection not started" in resp.text


def test_calendar_callback_success_is_friendly_html(client):
    with patch("app.routers.calendar.exchange_code_for_tokens", new=AsyncMock(return_value={})):
        resp = client.get("/api/calendar/callback?code=test-code")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Calendar connected" in resp.text
