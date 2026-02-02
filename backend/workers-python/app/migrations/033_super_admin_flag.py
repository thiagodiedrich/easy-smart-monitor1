"""
Migration 033: Flag is_superadmin e unicidade global do super admin.
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN DEFAULT FALSE NOT NULL;
            """))
            await db.commit()

            result = await db.execute(text("""
                SELECT id FROM users
                WHERE role @> '[0]'::jsonb
                ORDER BY id ASC
            """))
            rows = result.fetchall()
            if rows:
                super_id = rows[0][0]
                await db.execute(
                    text("UPDATE users SET is_superadmin = TRUE WHERE id = :id"),
                    {"id": super_id},
                )
                if len(rows) > 1:
                    await db.execute(text("""
                        UPDATE users
                        SET role = jsonb_build_object('role', 'admin')
                        WHERE id <> :id AND role @> '[0]'::jsonb
                    """), {"id": super_id})
            await db.commit()

            await db.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_users_superadmin
                ON users (is_superadmin)
                WHERE is_superadmin = TRUE;
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("DROP INDEX IF EXISTS uq_users_superadmin;"))
            await db.commit()
            await db.execute(text("""
                ALTER TABLE users
                DROP COLUMN IF EXISTS is_superadmin;
            """))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
