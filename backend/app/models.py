from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class Item(BaseModel):
    id: int
    title: str
    completed: bool = False
