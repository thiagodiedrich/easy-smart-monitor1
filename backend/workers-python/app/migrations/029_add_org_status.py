"""
Migration 029: Adicionar status em organizations
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
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'organization_status') THEN
                        CREATE TYPE organization_status AS ENUM ('active', 'inactive', 'blocked');
                    ELSE
                        ALTER TYPE organization_status ADD VALUE IF NOT EXISTS 'active';
                        ALTER TYPE organization_status ADD VALUE IF NOT EXISTS 'inactive';
                        ALTER TYPE organization_status ADD VALUE IF NOT EXISTS 'blocked';
                    END IF;
                END$$;
            """))
            await db.commit()

            await db.execute(text("""
                ALTER TABLE organizations
                ADD COLUMN IF NOT EXISTS status organization_status NOT NULL DEFAULT 'active';
            """))
            await db.commit()

            await db.execute(text("""
                UPDATE organizations
                SET status = 'active'
                WHERE status IS NULL;
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("""
                ALTER TABLE organizations
                DROP COLUMN IF EXISTS status;
            """))
            await db.execute(text("DROP TYPE IF EXISTS organization_status;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
