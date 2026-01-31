"""
Migration 007: Adicionar tenant_id em users e equipments

Fase 1 da evolução multi-tenant:
- Adiciona coluna tenant_id em users e equipments (nullable).
- Cria um tenant padrão (legacy) se não existir.
- Backfill tenant_id usando o tenant padrão.
- Cria índices e FKs sem forçar NOT NULL.
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

DEFAULT_TENANT_SLUG = "legacy"
DEFAULT_TENANT_NAME = "Legacy Tenant"


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Garantir tenant padrão
            await db.execute(text("""
                INSERT INTO tenants (name, slug, status)
                VALUES (:name, :slug, 'active')
                ON CONFLICT (slug) DO NOTHING;
            """), {"name": DEFAULT_TENANT_NAME, "slug": DEFAULT_TENANT_SLUG})
            await db.commit()

            # 2. Obter tenant_id padrão
            result = await db.execute(
                text("SELECT id FROM tenants WHERE slug = :slug"),
                {"slug": DEFAULT_TENANT_SLUG},
            )
            default_tenant_id = result.scalar_one()

            # 3. Adicionar coluna tenant_id em users
            await db.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
            """))
            await db.commit()

            # 4. Adicionar FK em users (se não existir)
            await db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'users_tenant_id_fkey'
                    ) THEN
                        ALTER TABLE users
                        ADD CONSTRAINT users_tenant_id_fkey
                        FOREIGN KEY (tenant_id) REFERENCES tenants(id);
                    END IF;
                END $$;
            """))
            await db.commit()

            # 5. Adicionar coluna tenant_id em equipments
            await db.execute(text("""
                ALTER TABLE equipments
                ADD COLUMN IF NOT EXISTS tenant_id INTEGER;
            """))
            await db.commit()

            # 6. Adicionar FK em equipments (se não existir)
            await db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'equipments_tenant_id_fkey'
                    ) THEN
                        ALTER TABLE equipments
                        ADD CONSTRAINT equipments_tenant_id_fkey
                        FOREIGN KEY (tenant_id) REFERENCES tenants(id);
                    END IF;
                END $$;
            """))
            await db.commit()

            # 7. Backfill users.tenant_id
            await db.execute(text("""
                UPDATE users
                SET tenant_id = :tenant_id
                WHERE tenant_id IS NULL;
            """), {"tenant_id": default_tenant_id})
            await db.commit()

            # 8. Backfill equipments.tenant_id a partir do usuário
            await db.execute(text("""
                UPDATE equipments e
                SET tenant_id = u.tenant_id
                FROM users u
                WHERE e.user_id = u.id
                  AND e.tenant_id IS NULL;
            """))
            await db.commit()

            # 9. Backfill restante com tenant padrão (fallback)
            await db.execute(text("""
                UPDATE equipments
                SET tenant_id = :tenant_id
                WHERE tenant_id IS NULL;
            """), {"tenant_id": default_tenant_id})
            await db.commit()

            # 10. Índices auxiliares
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_tenant_id
                ON users (tenant_id);
            """))
            await db.commit()

            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_equipments_tenant_id
                ON equipments (tenant_id);
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("ALTER TABLE equipments DROP CONSTRAINT IF EXISTS equipments_tenant_id_fkey;"))
            await db.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_tenant_id_fkey;"))
            await db.execute(text("ALTER TABLE equipments DROP COLUMN IF EXISTS tenant_id;"))
            await db.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS tenant_id;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
