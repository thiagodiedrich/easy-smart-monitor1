"""
Migration 022: Garantir default user_type = frontend
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # Garantir enum e valores esperados
            await db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_type WHERE typname = 'usertype'
                    ) THEN
                        CREATE TYPE usertype AS ENUM ('frontend', 'device');
                    END IF;
                END $$;
            """))
            await db.commit()

            await db.execute(text("""
                DO $$ BEGIN
                    ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'frontend';
                    ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'device';
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            await db.commit()

            # Backfill e default
            await db.execute(text("""
                UPDATE users
                SET user_type = 'frontend'
                WHERE user_type IS NULL;
            """))
            await db.commit()

            await db.execute(text("""
                ALTER TABLE users
                ALTER COLUMN user_type SET DEFAULT 'frontend';
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration (mantém default para evitar impacto)."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("SELECT 1;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
