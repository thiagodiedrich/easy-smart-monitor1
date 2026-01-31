"""
Migration 020: Audit logs (admin/global)
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NULL,
                    actor_user_id INTEGER NULL,
                    actor_role VARCHAR(50) NULL,
                    action VARCHAR(100) NOT NULL,
                    target_type VARCHAR(100) NOT NULL,
                    target_id VARCHAR(100) NULL,
                    metadata JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """))
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_id
                ON audit_logs (tenant_id);
            """))
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
                ON audit_logs (created_at);
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("DROP TABLE IF EXISTS audit_logs;"))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
