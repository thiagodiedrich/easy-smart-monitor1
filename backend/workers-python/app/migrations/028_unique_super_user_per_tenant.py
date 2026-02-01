"""
Migration 028: Garantir um único super user (role [0]) por tenant
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_users_super_by_tenant
                ON users (tenant_id)
                WHERE role @> '[0]'::jsonb;
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("DROP INDEX IF EXISTS uq_users_super_by_tenant;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
