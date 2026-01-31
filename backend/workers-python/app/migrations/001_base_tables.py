"""
Migration 001: Criar tabelas base

Cria as tabelas users, equipments, sensors e telemetry_data
a partir dos modelos SQLAlchemy. Deve rodar antes da 002 (hypertable).
"""
from app.core.database import engine, Base


async def upgrade():
    """Cria todas as tabelas base a partir dos modelos."""
    # Importar modelos para registrá-los em Base.metadata
    from app.models import User, Equipment, Sensor, TelemetryData  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tabelas base criadas (users, equipments, sensors, telemetry_data)")


async def downgrade():
    """Remove as tabelas base (ordem inversa por causa de FKs)."""
    from app.models import User, Equipment, Sensor, TelemetryData  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("⚠️  Tabelas base removidas")
