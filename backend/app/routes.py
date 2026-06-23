from fastapi import APIRouter, HTTPException, status

from .database import get_connection, row_to_item
from .models import Item, ItemCreate


router = APIRouter(prefix="/api", tags=["items"])


@router.get("/items", response_model=list[Item])
def list_items() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, completed FROM items ORDER BY id ASC"
        ).fetchall()
    return [row_to_item(row) for row in rows]


@router.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate) -> dict:
    title = payload.title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Item title cannot be blank.",
        )

    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO items (title, completed) VALUES (?, ?)",
            (title, 0),
        )
        row = connection.execute(
            "SELECT id, title, completed FROM items WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return row_to_item(row)
