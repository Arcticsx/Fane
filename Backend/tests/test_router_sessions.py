import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import api.router as router_module


@pytest.fixture
def client():
    return TestClient(router_module.app)


def test_recent_sessions_route_returns_recent_sessions(monkeypatch, client):
    expected = [{"id": 1, "persona": "Lyra", "updated_at": "2024-01-01T00:00:00"}]

    def fake_get_recent_sessions(conn):
        return expected

    monkeypatch.setattr(router_module, "get_recent_sessions", fake_get_recent_sessions)

    response = client.get("/sessions/recent")

    assert response.status_code == 200
    assert response.json() == {"sessions": expected}
