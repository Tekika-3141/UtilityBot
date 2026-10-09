import os
os.environ["DEV_AUTH_ENABLED"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from fastapi.testclient import TestClient
from app.main import app


def test_health_and_idor():
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/api/v1/guilds/999999999999999999/settings").status_code == 403


def test_dev_login_and_guild_list():
    with TestClient(app) as client:
        response = client.post("/api/v1/dev-login")
        assert response.status_code == 200
        assert client.get("/api/v1/guilds").json()[0]["manageable"] is True
