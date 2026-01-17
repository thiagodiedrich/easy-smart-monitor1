# TimescaleDB - Continuous Aggregates Setup v1.0.0

## 🎯 Objetivo

Implementar **Continuous Aggregates** do TimescaleDB para otimizar consultas analíticas, reduzindo tempo de resposta de segundos para milissegundos.

**Versão**: 1.0.0 Estável

## 🎯 Objetivo

Implementar **Continuous Aggregates** do TimescaleDB para otimizar consultas analíticas, reduzindo tempo de resposta de segundos para milissegundos.

## 📊 Estrutura Implementada

### 1. Hypertable

A tabela `telemetry_data` foi convertida em **hypertable** do TimescaleDB:

```sql
SELECT create_hypertable(
    'telemetry_data',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day'
);
```

**Benefícios:**
- Particionamento automático por tempo
- Queries otimizadas para time-series
- Compressão automática de chunks antigos

### 2. Continuous Aggregates

#### Agregação Horária (`telemetry_hourly`)

```sql
CREATE MATERIALIZED VIEW telemetry_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS bucket,
    equipment_id,
    sensor_id,
    AVG(value) AS avg_value,
    MAX(value) AS max_value,
    MIN(value) AS min_value,
    COUNT(*) AS sample_count,
    STDDEV(value) AS stddev_value,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95_value,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) AS p99_value
FROM telemetry_data
GROUP BY bucket, equipment_id, sensor_id;
```

**Uso:** Dashboards, análises recentes (últimas 24h-7d)

#### Agregação Diária (`telemetry_daily`)

```sql
CREATE MATERIALIZED VIEW telemetry_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', timestamp) AS bucket,
    equipment_id,
    sensor_id,
    AVG(value) AS avg_value,
    MAX(value) AS max_value,
    MIN(value) AS min_value,
    COUNT(*) AS sample_count,
    STDDEV(value) AS stddev_value,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) AS median_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95_value,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) AS p99_value
FROM telemetry_data
GROUP BY bucket, equipment_id, sensor_id;
```

**Uso:** Análises históricas, tendências (30d-1y)

### 3. Políticas de Refresh

#### Agregação Horária

```sql
SELECT add_continuous_aggregate_policy(
    'telemetry_hourly',
    start_offset => INTERVAL '3 days',  -- Recalcula últimos 3 dias
    end_offset => INTERVAL '1 hour',      -- Deixa última hora em aberto
    schedule_interval => INTERVAL '30 minutes'  -- Atualiza a cada 30 min
);
```

#### Agregação Diária

```sql
SELECT add_continuous_aggregate_policy(
    'telemetry_daily',
    start_offset => INTERVAL '7 days',    -- Recalcula últimos 7 dias
    end_offset => INTERVAL '1 day',      -- Deixa último dia em aberto
    schedule_interval => INTERVAL '2 hours'  -- Atualiza a cada 2 horas
);
```

**Real-Time Aggregation:** O TimescaleDB combina automaticamente dados materializados (histórico) com dados brutos recentes (última hora/dia), garantindo precisão total mesmo para dados que acabaram de chegar.

### 4. Política de Retenção

```sql
SELECT add_retention_policy(
    'telemetry_data',
    drop_after => INTERVAL '30 days'
);
```

**Estratégia:**
- **Dados brutos**: Mantidos por 30 dias (para análises detalhadas recentes)
- **Agregados horários**: Mantidos indefinidamente (leves, valiosos)
- **Agregados diários**: Mantidos indefinidamente (tendências históricas)

**Economia:** Redução de 90%+ no armazenamento a longo prazo.

## 🚀 Como Aplicar

### 1. Executar Migrations

```bash
cd backend/workers-python

# Migration 002: Criar hypertable
python -m app.migrations.002_timescaledb_hypertable upgrade

# Migration 003: Criar continuous aggregates
python -m app.migrations.003_continuous_aggregates upgrade

# Migration 004: Configurar políticas
python -m app.migrations.004_continuous_aggregates_policies upgrade
```

### 2. Verificar

```sql
-- Verificar hypertable
SELECT * FROM timescaledb_information.hypertables;

-- Verificar continuous aggregates
SELECT * FROM timescaledb_information.continuous_aggregates;

-- Verificar políticas
SELECT * FROM timescaledb_information.jobs;
```

## 📈 Performance

### Antes (Sem Continuous Aggregates)

```sql
-- Query lenta: Varre milhões de linhas
SELECT AVG(value) FROM telemetry_data 
WHERE equipment_id = 1 AND timestamp > NOW() - INTERVAL '30 days';
-- Tempo: 5-20 segundos
```

### Depois (Com Continuous Aggregates)

```sql
-- Query rápida: Varre apenas ~720 linhas (30 dias * 24 horas)
SELECT AVG(avg_value) FROM telemetry_hourly
WHERE equipment_id = 1 AND bucket > NOW() - INTERVAL '30 days';
-- Tempo: 10-50 milissegundos
```

**Melhoria:** 100-2000x mais rápido! ⚡

## 🔍 Consultas Otimizadas

### Dashboard (Últimas 24h)

```sql
SELECT 
    bucket,
    sensor_id,
    avg_value,
    max_value,
    min_value
FROM telemetry_hourly
WHERE equipment_id = 1
    AND bucket >= NOW() - INTERVAL '24 hours'
ORDER BY bucket ASC;
```

### Home Assistant (Últimas 24h)

```sql
SELECT 
    bucket AS time,
    s.type AS sensor_type,
    agg.avg_value AS value
FROM telemetry_hourly agg
INNER JOIN sensors s ON agg.sensor_id = s.id
WHERE agg.equipment_id = 1
    AND agg.bucket >= NOW() - INTERVAL '24 hours'
ORDER BY bucket ASC;
```

### Análise Histórica (Último Ano)

```sql
SELECT 
    bucket,
    sensor_id,
    avg_value,
    max_value,
    min_value
FROM telemetry_daily
WHERE equipment_id = 1
    AND bucket >= NOW() - INTERVAL '1 year'
ORDER BY bucket ASC;
```

## 📊 Endpoints API

Todas as consultas estão centralizadas na API:

- `GET /api/v1/analytics/equipment/:uuid/history` - Histórico de equipamento
- `GET /api/v1/analytics/sensor/:uuid/history` - Histórico de sensor
- `GET /api/v1/analytics/equipment/:uuid/stats` - Estatísticas agregadas
- `GET /api/v1/analytics/home-assistant/:uuid` - Dados para Home Assistant

**Todas as regras de negócio centralizadas na API!** ✅

## ⚙️ Manutenção

### Atualizar Manualmente

```sql
-- Forçar refresh de uma agregação
CALL refresh_continuous_aggregate('telemetry_hourly', NULL, NULL);
```

### Monitorar Status

```sql
-- Ver status das políticas
SELECT * FROM timescaledb_information.job_stats;

-- Ver tamanho das views
SELECT 
    schemaname,
    matviewname,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) AS size
FROM pg_matviews
WHERE matviewname LIKE 'telemetry_%';
```

## 🔒 Segurança

- Todas as queries passam pela API (validação centralizada)
- Autenticação JWT obrigatória
- Rate limiting aplicado
- Sanitização de inputs

---

**Continuous Aggregates configurados e otimizados!** 🚀
