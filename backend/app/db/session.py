"""
Gestión de la conexión a MariaDB.

- AsyncSessionLocal: para los endpoints FastAPI (async).
- SyncSession:       para las tools de LangChain (sync, llamadas desde
                     dentro de los nodos del grafo).
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_USER     = os.getenv("DB_USER", "claims_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "claims_dev")
DB_HOST     = os.getenv("DB_HOST", "mariadb")
DB_PORT     = os.getenv("DB_PORT", "3306")
DB_NAME     = os.getenv("DB_NAME", "smart_claims")


# ── Async (FastAPI) ────────────────────────────────────────────────────────

ASYNC_DATABASE_URL = (
    f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# ── Sync (LangChain tools) ─────────────────────────────────────────────────

SYNC_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
sync_engine = create_engine(SYNC_DATABASE_URL, echo=False, pool_pre_ping=True)
SyncSession = sessionmaker(bind=sync_engine, expire_on_commit=False)


# ── Base declarativa ──────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Lifespan ──────────────────────────────────────────────────────────────

async def init_db():
    """Verifica la conexión a la BD al arrancar."""
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: None)


async def get_db():
    """Dependency injection async para FastAPI."""
    async with AsyncSessionLocal() as session:
        yield session
