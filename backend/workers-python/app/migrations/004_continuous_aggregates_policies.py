"""
Migration 004: Configurar Políticas de Continuous Aggregates

Configura refresh automático e políticas de retenção.
"""
from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def upgrade():
    """Aplica a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Política de Refresh para Agregação Horária
            # Atualiza a cada 30 minutos, mantém janela de 3 dias para dados atrasados
            await db.execute(text("""
                SELECT add_continuous_aggregate_policy(
                    'telemetry_hourly',
                    start_offset => INTERVAL '3 days',
                    end_offset => INTERVAL '1 hour',
                    schedule_interval => INTERVAL '30 minutes',
                    if_not_exists => TRUE
                );
            """))
            
            # 2. Política de Refresh para Agregação Diária
            # Atualiza a cada 2 horas, mantém janela de 7 dias para dados atrasados
            await db.execute(text("""
                SELECT add_continuous_aggregate_policy(
                    'telemetry_daily',
                    start_offset => INTERVAL '7 days',
                    end_offset => INTERVAL '1 day',
                    schedule_interval => INTERVAL '2 hours',
                    if_not_exists => TRUE
                );
            """))
            
            # 3. Política de Retenção de Dados Brutos
            # Mantém dados brutos por 30 dias, depois remove automaticamente
            # Os agregados (horário/diário) permanecem intactos
            await db.execute(text("""
                SELECT add_retention_policy(
                    'telemetry_data',
                    drop_after => INTERVAL '30 days',
                    if_not_exists => TRUE
                );
            """))
            
            await db.commit()
            
            print("✅ Políticas de Continuous Aggregates configuradas!")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Erro ao configurar políticas: {e}")
            raise


async def downgrade():
    """Reverte a migration."""
    async with AsyncSessionLocal() as db:
        try:
            # Remover políticas
            await db.execute(text("""
                SELECT remove_retention_policy('telemetry_data', if_exists => TRUE);
            """))
            
            await db.execute(text("""
                SELECT remove_continuous_aggregate_policy('telemetry_daily', if_exists => TRUE);
            """))
            
            await db.execute(text("""
                SELECT remove_continuous_aggregate_policy('telemetry_hourly', if_exists => TRUE);
            """))
            
            await db.commit()
            
            print("✅ Políticas removidas")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Erro ao reverter: {e}")
            raise
