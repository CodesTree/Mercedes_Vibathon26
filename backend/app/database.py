import os
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DATABASE_URL = "sqlite:///./app.db"
SEED_ITEM = "Connect the frontend to FastAPI"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_database_path() -> Path:
    database_url = get_database_url()
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// DATABASE_URL values are supported in this starter.")

    raw_path = database_url.removeprefix("sqlite:///")
    return Path(raw_path).expanduser()


def get_connection() -> sqlite3.Connection:
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        existing_count = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if existing_count == 0:
            connection.execute(
                "INSERT INTO items (title, completed) VALUES (?, ?)",
                (SEED_ITEM, 0),
            )


def row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "completed": bool(row["completed"]),
    }
