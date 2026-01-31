"""
Migration 003: Criar Continuous Aggregates

Cria views materializadas contínuas para agregações horárias e diárias
de telemetria, otimizando consultas analíticas.

Nota: CREATE MATERIALIZED VIEW ... WITH DATA não pode rodar dentro de transação;
usamos um engine em AUTOCOMMIT para o DDL.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings


async def upgrade():
    """Aplica a migration."""
    # CREATE MATERIALIZED VIEW ... WITH DATA exige execução fora de transação (AUTOCOMMIT)
    autocommit_engine = create_async_engine(
        settings.DATABASE_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    async with autocommit_engine.connect() as conn:
        try:
            # 1. Agregação Horária (para dashboards e análises recentes)
            await conn.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 hour', timestamp) AS bucket,
                    equipment_id,
                    sensor_id,
                    AVG(value) AS avg_value,
                    MAX(value) AS max_value,
                    MIN(value) AS min_value,
                    COUNT(*) AS sample_count,
                    COUNT(DISTINCT DATE_TRUNC('minute', timestamp)) AS active_minutes,
                    STDDEV(value) AS stddev_value,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_value,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95_value,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) AS p99_value
                FROM telemetry_data
                GROUP BY 
                    time_bucket('1 hour', timestamp),
                    equipment_id,
                    sensor_id;
            """))

            # 2. Agregação Diária (para análises históricas e tendências)
            await conn.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_daily
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 day', timestamp) AS bucket,
                    equipment_id,
                    sensor_id,
                    AVG(value) AS avg_value,
                    MAX(value) AS max_value,
                    MIN(value) AS min_value,
                    COUNT(*) AS sample_count,
                    COUNT(DISTINCT DATE_TRUNC('hour', timestamp)) AS active_hours,
                    STDDEV(value) AS stddev_value,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_value,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95_value,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) AS p99_value
                FROM telemetry_data
                GROUP BY 
                    time_bucket('1 day', timestamp),
                    equipment_id,
                    sensor_id;
            """))

            # 3. Índices para otimizar queries nas views
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_equipment_bucket 
                ON telemetry_hourly (equipment_id, bucket DESC);
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_sensor_bucket 
                ON telemetry_hourly (sensor_id, bucket DESC);
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_daily_equipment_bucket 
                ON telemetry_daily (equipment_id, bucket DESC);
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_daily_sensor_bucket 
                ON telemetry_daily (sensor_id, bucket DESC);
            """))

            print("✅ Continuous Aggregates criadas com sucesso!")

        except Exception as e:
            print(f"❌ Erro ao criar continuous aggregates: {e}")
            raise
    await autocommit_engine.dispose()


async def downgrade():
    """Reverte a migration."""
    autocommit_engine = create_async_engine(
        settings.DATABASE_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    async with autocommit_engine.connect() as conn:
        try:
            await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS telemetry_daily CASCADE;"))
            await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly CASCADE;"))
            print("✅ Continuous Aggregates removidas")
        except Exception as e:
            print(f"❌ Erro ao reverter: {e}")
            raise
    await autocommit_engine.dispose()
