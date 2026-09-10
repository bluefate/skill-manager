"""Tests for the FastAPI application."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_skills_manager.config import Settings
from agent_skills_manager.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(skills_dir=tmp_path / "hub", config_dir=tmp_path / "config")
    app = create_app(settings)
    return TestClient(app)


def test_home(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Agent Skills Manager" in response.text
    assert "One place for all your agent skills" in response.text


def test_dashboard(client: TestClient) -> None:
    response = client.get("/app")
    assert response.status_code == 200
    assert "Agent Skills Manager" in response.text
    assert "Central Skills" in response.text
    assert "Central hub location" in response.text
    assert "custom path" in response.text
    assert "/hub" in response.text


@pytest.mark.parametrize("path", ["/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"])
def test_apple_touch_icon(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_skills_crud(client: TestClient) -> None:
    response = client.post("/api/skills", json={
        "name": "test-skill",
        "description": "A test skill",
        "tags": ["test"],
        "path": "/",
    })
    assert response.status_code == 200
    assert response.json()["name"] == "test-skill"

    response = client.get("/api/skills")
    assert response.status_code == 200
    skills = response.json()
    assert len(skills) == 1
    assert skills[0]["name"] == "test-skill"

    response = client.get("/api/skills/test-skill")
    assert response.status_code == 200
    assert response.json()["description"] == "A test skill"

    response = client.delete("/api/skills/test-skill")
    assert response.status_code == 200

    response = client.get("/api/skills")
    assert response.json() == []


def test_targets_list(client: TestClient) -> None:
    response = client.get("/api/targets")
    assert response.status_code == 200
    targets = response.json()
    assert len(targets) >= 4
    assert any(t["name"] == "Cursor" for t in targets)


def test_default_targets(client: TestClient) -> None:
    response = client.get("/api/targets/defaults")
    assert response.status_code == 200
    targets = response.json()
    assert len(targets) >= 4
    ids = [t["id"] for t in targets]
    assert len(set(ids)) == len(ids)

    response = client.post("/api/targets/defaults", json=ids[:2])
    assert response.status_code == 200

    response = client.get("/api/targets")
    assert response.status_code == 200
    active = response.json()
    assert len(active) == 2


def test_target_preview(client: TestClient) -> None:
    targets = client.get("/api/targets").json()
    target = next(t for t in targets if t["name"] == "Codex")
    response = client.get(
        "/api/targets/preview",
        params={"target_id": target["id"], "move_existing": True, "conflict_strategy": "rename"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "target" in data
    assert "can_symlink" in data
