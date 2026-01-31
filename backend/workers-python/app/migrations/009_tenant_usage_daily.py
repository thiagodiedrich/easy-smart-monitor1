"""
Migration 009: Tabela de uso diário por tenant (billing-ready)

Fase 4 (Observabilidade + Billing):
- Cria tabela tenant_usage_daily para agregação diária de uso.
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS tenant_usage_daily (
                    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    day DATE NOT NULL,
                    items_count BIGINT NOT NULL DEFAULT 0,
                    sensors_count BIGINT NOT NULL DEFAULT 0,
                    bytes_ingested BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (tenant_id, day)
                );
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("DROP TABLE IF EXISTS tenant_usage_daily;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
