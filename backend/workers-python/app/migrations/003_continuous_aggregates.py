"""
Migration 003: Criar Continuous Aggregates

Cria views materializadas contínuas para agregações horárias e diárias
de telemetria, otimizando consultas analíticas.
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Agregação Horária (para dashboards e análises recentes)
            await db.execute(text("""
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
            await db.execute(text("""
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
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_equipment_bucket 
                ON telemetry_hourly (equipment_id, bucket DESC);
            """))
            
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_sensor_bucket 
                ON telemetry_hourly (sensor_id, bucket DESC);
            """))
            
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_daily_equipment_bucket 
                ON telemetry_daily (equipment_id, bucket DESC);
            """))
            
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_daily_sensor_bucket 
                ON telemetry_daily (sensor_id, bucket DESC);
            """))
            
            await db.commit()
            
            print("✅ Continuous Aggregates criadas com sucesso!")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Erro ao criar continuous aggregates: {e}")
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text("DROP MATERIALIZED VIEW IF EXISTS telemetry_daily CASCADE;"))
            await db.execute(text("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly CASCADE;"))
            await db.commit()
            
            print("✅ Continuous Aggregates removidas")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Erro ao reverter: {e}")
            raise
