import importlib

from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")

    import app.database as database
    import app.main as main

    importlib.reload(database)
    importlib.reload(main)
    database.init_db()

    return TestClient(main.app)


def test_items_endpoint_starts_with_seed_item(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/items")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "title": "Connect the frontend to FastAPI", "completed": False}
    ]


def test_create_item_persists_to_sqlite(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    create_response = client.post("/api/items", json={"title": "Run Playwright tests"})
    list_response = client.get("/api/items")

    assert create_response.status_code == 201
    assert create_response.json() == {
        "id": 2,
        "title": "Run Playwright tests",
        "completed": False,
    }
    assert list_response.json()[-1] == create_response.json()
