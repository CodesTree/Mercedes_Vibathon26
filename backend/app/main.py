import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

load_dotenv()

from .database import SessionLocal, init_db
from .seed import seed
from .services.telegram import run_poller
from .routers.messages import router as messages_router
from .routers.contacts import router as contacts_router
from .routers.settings import router as settings_router
from .routers.car import router as car_router
from .routers.calendar import router as calendar_router
from .routers.navigation import router as nav_router
from .routers.automations import router as automations_router
from .routers.assistant import router as assistant_router


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create tables
    init_db()
    # 2. Seed demo data (idempotent)
    db: Session = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    # 3. Start Telegram long-poll background task
    poller_task = asyncio.create_task(run_poller())
    yield
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="CarPa In-Car AI Co-Pilot",
    description="Mercedes in-car AI assistant — Telegram triage, late responder, cabin cooling.",
    version="3.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messages_router)
app.include_router(contacts_router)
app.include_router(settings_router)
app.include_router(car_router)
app.include_router(calendar_router)
app.include_router(nav_router)
app.include_router(automations_router)
app.include_router(assistant_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "3.2.0"}
