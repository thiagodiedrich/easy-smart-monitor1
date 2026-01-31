"""
Migration 010: Plans e limites por tenant (billing/quotas)

Fase 5:
- Cria tabela plans (limites por plano)
- Cria tabela tenant_limits (override por tenant)
- Garante plano padrão e associa tenants sem plano
"""
import os
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


DEFAULT_PLAN_CODE = os.getenv("DEFAULT_PLAN_CODE", "legacy")
DEFAULT_PLAN_NAME = os.getenv("DEFAULT_PLAN_NAME", "Legacy Plan")
DEFAULT_PLAN_ITEMS_PER_DAY = os.getenv("DEFAULT_PLAN_ITEMS_PER_DAY")
DEFAULT_PLAN_SENSORS_PER_DAY = os.getenv("DEFAULT_PLAN_SENSORS_PER_DAY")
DEFAULT_PLAN_BYTES_PER_DAY = os.getenv("DEFAULT_PLAN_BYTES_PER_DAY")


def _to_int(value):
    try:
        return int(value) if value is not None and str(value).isdigit() else None
    except Exception:
        return None


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS plans (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(150) NOT NULL,
                    items_per_day BIGINT NULL,
                    sensors_per_day BIGINT NULL,
                    bytes_per_day BIGINT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """))
            await db.commit()

            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS tenant_limits (
                    tenant_id INTEGER PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
                    items_per_day BIGINT NULL,
                    sensors_per_day BIGINT NULL,
                    bytes_per_day BIGINT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """))
            await db.commit()

            # Plano padrão
            await db.execute(text("""
                INSERT INTO plans (code, name, items_per_day, sensors_per_day, bytes_per_day)
                VALUES (:code, :name, :items, :sensors, :bytes)
                ON CONFLICT (code) DO NOTHING;
            """), {
                "code": DEFAULT_PLAN_CODE,
                "name": DEFAULT_PLAN_NAME,
                "items": _to_int(DEFAULT_PLAN_ITEMS_PER_DAY),
                "sensors": _to_int(DEFAULT_PLAN_SENSORS_PER_DAY),
                "bytes": _to_int(DEFAULT_PLAN_BYTES_PER_DAY),
            })
            await db.commit()

            # Associar plano padrão a tenants sem plan_code
            await db.execute(text("""
                UPDATE tenants
                SET plan_code = :plan_code
                WHERE plan_code IS NULL OR plan_code = '';
            """), {"plan_code": DEFAULT_PLAN_CODE})
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("DROP TABLE IF EXISTS tenant_limits;"))
            await db.execute(text("DROP TABLE IF EXISTS plans;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
