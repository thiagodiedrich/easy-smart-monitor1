"""
Migrations para TimescaleDB.

Ordem de execução:
1. 002_timescaledb_hypertable - Converte tabela em hypertable
2. 003_continuous_aggregates - Cria continuous aggregates
3. 004_continuous_aggregates_policies - Configura políticas
"""
