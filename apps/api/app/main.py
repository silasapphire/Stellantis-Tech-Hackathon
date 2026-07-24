from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from agents.graph.mcp_client import mcp_session  # noqa: E402  (must follow load_dotenv)
from app.routers import assets, chat, telemetry  # noqa: E402
from app.scheduler import start_scheduler  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_session() as session:
        app.state.mcp_session = session
        scheduler = start_scheduler(session)
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Smart Connected Diagnostics API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry.router)
app.include_router(assets.router)
app.include_router(chat.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
