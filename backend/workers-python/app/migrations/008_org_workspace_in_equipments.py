"""
Migration 008: Adicionar organization_id e workspace_id em equipments

Fase 2 da evolução multi-tenant:
- Adiciona organization_id e workspace_id em equipments (nullable).
- Cria FKs e índices auxiliares.
- Não altera dados existentes.
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Adicionar colunas
            await db.execute(text("""
                ALTER TABLE equipments
                ADD COLUMN IF NOT EXISTS organization_id INTEGER,
                ADD COLUMN IF NOT EXISTS workspace_id INTEGER;
            """))
            await db.commit()

            # 2. FKs (se não existirem)
            await db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'equipments_organization_id_fkey'
                    ) THEN
                        ALTER TABLE equipments
                        ADD CONSTRAINT equipments_organization_id_fkey
                        FOREIGN KEY (organization_id) REFERENCES organizations(id);
                    END IF;
                END $$;
            """))
            await db.commit()

            await db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'equipments_workspace_id_fkey'
                    ) THEN
                        ALTER TABLE equipments
                        ADD CONSTRAINT equipments_workspace_id_fkey
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id);
                    END IF;
                END $$;
            """))
            await db.commit()

            # 3. Índices auxiliares
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_equipments_organization_id
                ON equipments (organization_id);
            """))
            await db.commit()

            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_equipments_workspace_id
                ON equipments (workspace_id);
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("ALTER TABLE equipments DROP CONSTRAINT IF EXISTS equipments_workspace_id_fkey;"))
            await db.execute(text("ALTER TABLE equipments DROP CONSTRAINT IF EXISTS equipments_organization_id_fkey;"))
            await db.execute(text("ALTER TABLE equipments DROP COLUMN IF EXISTS workspace_id;"))
            await db.execute(text("ALTER TABLE equipments DROP COLUMN IF EXISTS organization_id;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
