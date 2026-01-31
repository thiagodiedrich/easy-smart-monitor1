"""
Migration 023: Corrigir enum userstatus (active/inactive/blocked)
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_type WHERE typname = 'userstatus'
                    ) THEN
                        CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'blocked');
                    END IF;
                END $$;
            """))
            await db.commit()

            await db.execute(text("""
                DO $$ BEGIN
                    ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'active';
                    ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'inactive';
                    ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'blocked';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration (não remove enum para evitar impacto)."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("SELECT 1;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
