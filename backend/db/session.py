import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_USER = os.getenv("DB_USER", "claims_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "claims_dev")
DB_HOST = os.getenv("DB_HOST", "mariadb")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "smart_claims")

DATABASE_URL = (
    f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Comprova la connexió a la BD en arrencar l'app."""
    async with engine.begin() as conn:
        # Simplement verifica que la connexió funciona
        await conn.run_sync(lambda c: None)


async def get_db():
    """Dependency injection per a FastAPI."""
    async with AsyncSessionLocal() as session:
        yield session
