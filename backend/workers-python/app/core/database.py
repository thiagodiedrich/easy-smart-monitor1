"""
Configuração e gerenciamento de conexões com banco de dados PostgreSQL.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Base para modelos SQLAlchemy
Base = declarative_base()

# Engine assíncrono
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obter sessão de banco de dados.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Inicializa o banco de dados."""
    try:
        async with engine.begin() as conn:
            from app.models import (  # noqa: F401
                user,
                equipment,
                sensor,
                telemetry_data,
            )
            
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error("Erro ao inicializar banco de dados", exc_info=e)
        raise


async def close_db() -> None:
    """Fecha todas as conexões com o banco de dados."""
    try:
        await engine.dispose()
        logger.info("Conexões com banco de dados fechadas")
    except Exception as e:
        logger.error("Erro ao fechar conexões com banco de dados", exc_info=e)
