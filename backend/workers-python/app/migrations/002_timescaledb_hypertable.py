"""
Migration 002: Configurar TimescaleDB Hypertable

Converte a tabela telemetry_data em hypertable do TimescaleDB
para suportar Continuous Aggregates e otimizações de time-series.
"""
import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Criar extensão TimescaleDB (se não existir)
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            await db.commit()

            # 2. Remover PK apenas em id (TimescaleDB exige que a coluna de particionamento esteja na PK/unique)
            await db.execute(text("""
                ALTER TABLE telemetry_data DROP CONSTRAINT IF EXISTS telemetry_data_pkey;
            """))
            await db.commit()

            # 3. Converter telemetry_data em hypertable
            await db.execute(text("""
                SELECT create_hypertable(
                    'telemetry_data',
                    'timestamp',
                    chunk_time_interval => INTERVAL '1 day',
                    if_not_exists => TRUE
                );
            """))
            await db.commit()

            # 4. Recriar PK composta (timestamp, id) para unicidade e compatibilidade
            await db.execute(text("""
                ALTER TABLE telemetry_data ADD CONSTRAINT telemetry_data_pkey
                PRIMARY KEY (timestamp, id);
            """))
            await db.commit()

            # 5. Criar índices otimizados para queries analíticas
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_equipment_timestamp 
                ON telemetry_data (equipment_id, timestamp DESC);
            """))
            
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_sensor_timestamp 
                ON telemetry_data (sensor_id, timestamp DESC);
            """))
            
            await db.commit()
            
            print("✅ TimescaleDB hypertable criada com sucesso!")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Erro ao criar hypertable: {e}")
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # Remover hypertable (converte de volta para tabela normal)
            await db.execute(text("""
                SELECT drop_chunks('telemetry_data', INTERVAL '0 days');
            """))
            
            # Nota: Não podemos "desconverter" hypertable facilmente
            # A tabela permanece, mas sem otimizações do TimescaleDB
            await db.commit()
            
            print("⚠️  Hypertable removida (tabela permanece)")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Erro ao reverter: {e}")
            raise
