"""
Smart-Claims Agent — Backend entrypoint.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import init_db
from app.routers import claims, agents, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Smart-Claims Agent",
    description="MVP d'agent agèntic per a la gestió de sinistres — Seguros Pepín",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(claims.router, prefix="/api/v1/claims", tags=["claims"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
