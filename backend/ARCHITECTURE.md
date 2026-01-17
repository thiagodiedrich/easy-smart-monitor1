# Arquitetura do Backend - Easy Smart Monitor v1.0.0

## 📐 Visão Geral

Este documento descreve a arquitetura do backend da API Easy Smart Monitor v1.0.0, implementando o **Claim Check Pattern** e **TimescaleDB Continuous Aggregates** para processar payloads grandes de telemetria de forma escalável.

## 🏗️ Arquitetura de Alto Nível

```
┌─────────────┐
│   Cliente   │ (Home Assistant Integration)
│             │
└──────┬──────┘
       │ HTTPS
       │ JWT Bearer Token
       │ Payload: 1-10MB (GZIP comprimido)
       ▼
┌─────────────────────────────────────┐
│   API Gateway (Node.js + Fastify)   │
│  - Recebe requisições HTTP          │
│  - Validação rápida                  │
│  - Autenticação JWT                  │
│  - Rate Limiting (Redis)             │
│  - Salva arquivo em MinIO (streaming)│
│  - Gera Claim Check                 │
│  - Endpoints Analytics (TimescaleDB) │
└──────┬──────────────────────────────┘
       │
       ├─────────────────┬─────────────────┬─────────────────┐
       ▼                 ▼                 ▼                 ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   MinIO     │  │    Kafka    │  │    Redis    │  │ TimescaleDB  │
│             │  │             │  │             │  │             │
│ - Arquivos  │  │ - Claim     │  │ - Rate      │  │ - Dados     │
│   1-10MB    │  │   Checks    │  │   Limit     │  │   brutos    │
│ - GZIP      │  │   ~1KB      │  │ - Cache     │  │ - Continuous│
│ - Retenção  │  │ - 100K+     │  │             │  │   Aggregates│
│   7 dias    │  │   msg/s     │  │             │  │ - Queries   │
└──────┬──────┘  └──────┬──────┘  └─────────────┘  │   otimizadas│
       │                 │                         └──────┬──────┘
       │                 ▼                                 │
       │         ┌─────────────────────────────────────┐  │
       │         │   Python Workers (Múltiplos)        │  │
       │         │  - Consomem Claim Check do Kafka     │  │
       │         │  - Baixam arquivo do MinIO          │  │
       │         │  - Processam em lotes                │  │
       │         │  - Criam/atualizam equipamentos      │  │
       │         │  - Bulk inserts no TimescaleDB       │  │
       │         │  - Removem arquivo (opcional)        │  │
       │         └──────┬───────────────────────────────┘  │
       │                │                                    │
       └────────────────┼──────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │   TimescaleDB    │
              │  - Hypertable    │
              │  - Continuous    │
              │    Aggregates    │
              │  - Queries       │
              │    otimizadas    │
              └─────────────────┘
```

## 🎯 Claim Check Pattern

### Conceito

O **Claim Check Pattern** resolve o problema de payloads grandes no Kafka:

1. **Problema**: Kafka não é eficiente com mensagens grandes (> 1MB)
2. **Solução**: Salvar payload em storage, enviar apenas referência no Kafka
3. **Benefício**: Kafka processa milhões de mensagens pequenas (~1KB)

### Fluxo Detalhado

#### 1. Recebimento (Gateway)

```javascript
// Cliente envia payload grande (1-10MB)
POST /api/v1/telemetry/bulk
[ { equip_uuid: "...", sensor: [...] } ]

// Gateway:
// 1. Valida (JWT, schema, rate limit)
// 2. Salva arquivo em MinIO (streaming, comprimido GZIP)
// 3. Gera Claim Check:
{
  claim_check: "telemetry/2024-01-15-10-30-00/uuid.json.gz",
  storage_type: "minio",
  file_size: 1500000,
  original_size: 5000000
}
// 4. Envia Claim Check para Kafka (~1KB)
// 5. Responde 202 Accepted (imediato)
```

#### 2. Processamento (Worker)

```python
# Worker consome Claim Check do Kafka
claim_check = {
  "claim_check": "telemetry/2024-01-15-10-30-00/uuid.json.gz",
  "file_size": 1500000
}

# 1. Baixa arquivo do MinIO
data = await storage_client.download_file(claim_check['claim_check'])

# 2. Descomprime GZIP
# 3. Processa telemetria
result = await processor.process_bulk(user_id, data, db)

# 4. Insere no TimescaleDB (bulk)
# 5. Remove arquivo (opcional)
```

## 📊 TimescaleDB Continuous Aggregates

### Conceito

**Continuous Aggregates** pré-calculam agregações automaticamente:

1. **Problema**: Queries analíticas em bilhões de linhas são lentas
2. **Solução**: Agregações pré-calculadas (horária/diária)
3. **Benefício**: Queries 100-2000x mais rápidas (milissegundos)

### Agregações Implementadas

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

### Políticas Automáticas

#### Refresh Automático

- **Horária**: Atualiza a cada 30 minutos
- **Diária**: Atualiza a cada 2 horas
- **Real-Time**: Combina dados materializados com dados brutos recentes

#### Retenção de Dados

- **Dados brutos**: 30 dias (depois removidos automaticamente)
- **Agregados**: Mantidos indefinidamente (leves, valiosos)

## 🎯 Componentes Principais

### 1. API Gateway (Node.js + Fastify)

**Responsabilidades:**
- Receber requisições HTTP
- Validar autenticação JWT
- Rate limiting (Redis)
- Salvar arquivo em MinIO (streaming)
- Gerar Claim Check
- Enviar Claim Check para Kafka
- Consultas Analytics (TimescaleDB)
- Responder imediatamente ao cliente

**Tecnologias:**
- Fastify (framework web)
- @fastify/jwt (autenticação)
- minio (Object Storage client)
- kafkajs (produtor Kafka)
- ioredis (rate limiting)
- pg (PostgreSQL client para analytics)

**Performance:**
- Latência: 10-50ms (salva local, não bloqueia)
- Throughput: 10,000+ req/s
- Streaming: Não consome memória excessiva

### 2. Object Storage (MinIO)

**Configuração:**
- **Bucket**: `telemetry-raw`
- **Estrutura**: `telemetry/YYYY-MM-DD-HH-MM-SS/uuid.json.gz`
- **Compressão**: GZIP (70-85% de redução)
- **Retenção**: 7 dias (configurável)
- **Acesso**: API (porta 9000) e Console (porta 9001)

**Benefícios:**
- Armazena payloads grandes sem impacto no Kafka
- Permite reprocessamento
- Serve como Data Lake
- Custo baixo (storage local)

### 3. Message Broker (Apache Kafka)

**Configuração:**
- **Tópico**: `telemetry.raw`
- **Partições**: 3 (para paralelismo)
- **Tamanho Mensagem**: ~1KB (apenas Claim Check)
- **Throughput**: 100,000+ msg/s
- **Retenção**: 7 dias

**Benefícios:**
- Processa milhões de mensagens pequenas
- Não engasga com payloads grandes
- Distribui carga entre workers
- Retry automático

### 4. Workers Python

**Responsabilidades:**
- Consumir Claim Check do Kafka
- Baixar arquivo do MinIO
- Descomprimir GZIP
- Processar telemetria
- Inserir no TimescaleDB (bulk)
- Remover arquivo após processamento

**Tecnologias:**
- kafka-python (consumidor)
- minio (cliente MinIO)
- orjson (JSON rápido)
- SQLAlchemy (async)
- asyncpg (PostgreSQL)

**Escalabilidade:**
- Múltiplos workers (2+ réplicas)
- Processamento em lotes
- Bulk inserts otimizados

### 5. Banco de Dados TimescaleDB

**Estrutura:**
- `users`: Autenticação
- `equipments`: Dispositivos
- `sensors`: Sensores
- `telemetry_data`: Dados de telemetria (hypertable)
- `telemetry_hourly`: Agregação horária (continuous aggregate)
- `telemetry_daily`: Agregação diária (continuous aggregate)

**Otimizações:**
- Hypertable com chunks de 1 dia
- Índices compostos
- Bulk inserts
- Connection pooling
- Continuous Aggregates automáticos

## 🔄 Fluxo de Dados Completo

### Cenário: Cliente envia 50 dispositivos (100MB)

1. **Cliente → Gateway** (HTTP POST, 100MB GZIP = ~30MB)
2. **Gateway valida** (JWT, schema, rate limit) - 5ms
3. **Gateway salva em MinIO** (streaming, comprimido) - 200ms
4. **Gateway gera Claim Check** - 1ms
5. **Gateway → Kafka** (Claim Check ~1KB) - 10ms
6. **Gateway → Cliente** (202 Accepted) - **Total: ~216ms** ✅

7. **Kafka → Worker** (Claim Check) - 5ms
8. **Worker baixa do MinIO** - 150ms
9. **Worker descomprime** - 50ms
10. **Worker processa** - 500ms
11. **Worker insere no DB** - 300ms
12. **Continuous Aggregates atualizam** - Automático (background)
13. **Worker remove arquivo** - 10ms
14. **Worker commita offset** - 5ms

**Total processamento**: ~1 segundo (assíncrono, não bloqueia cliente)

### Consulta Analytics (Dashboard)

1. **Cliente → Gateway** (GET /analytics/equipment/:uuid/history)
2. **Gateway valida** (JWT) - 5ms
3. **Gateway consulta TimescaleDB** (Continuous Aggregate) - 10-50ms
4. **Gateway → Cliente** (JSON response) - **Total: 15-55ms** ✅

**Sem Continuous Aggregates**: 5-20 segundos ❌
**Com Continuous Aggregates**: 10-50 milissegundos ✅

## 📊 Performance

### Benchmarks Estimados

- **Throughput Gateway**: 10,000+ requisições/segundo
- **Latência Gateway**: 10-50ms (p95)
- **Throughput Kafka**: 100,000+ mensagens/segundo
- **Throughput Workers**: 1,000-2,000 arquivos/segundo por worker
- **Tamanho Kafka**: ~1KB por mensagem (vs 1-10MB antes)
- **Queries Analytics**: 10-50ms (vs 5-20s antes)

### Otimizações

- **Streaming**: Gateway não carrega payload completo na memória
- **Compressão**: GZIP reduz 70-85% do tamanho
- **Bulk Inserts**: Lotes de 1000 registros
- **Processamento em Lotes**: 100 mensagens por vez
- **Connection Pooling**: Pool de 20 conexões
- **Continuous Aggregates**: Pré-cálculo automático

## 🔐 Segurança

### Implementado

- ✅ JWT tokens com expiração curta
- ✅ Rate limiting por IP e usuário
- ✅ Validação rigorosa de dados
- ✅ HTTPS obrigatório em produção
- ✅ Sanitização de inputs
- ✅ Isolamento de storage
- ✅ Todas as regras de negócio centralizadas na API

### Boas Práticas

- Tokens JWT com expiração de 15 minutos
- Refresh tokens com 7 dias
- Rate limiting configurável
- Logs estruturados para auditoria
- Arquivos com metadados (user_id, request_id)

## 📈 Escalabilidade

### Horizontal Scaling

- **Gateway**: Múltiplas instâncias atrás de load balancer
- **Workers**: Múltiplos workers (escalam facilmente)
- **Kafka**: Cluster mode para alta disponibilidade
- **MinIO**: Cluster mode para alta disponibilidade
- **Database**: Read replicas para consultas

### Vertical Scaling

- Aumentar recursos de workers para processamento pesado
- Aumentar partições do Kafka para mais paralelismo
- Aumentar pool de conexões do banco

## 🚀 Deploy

### Docker Compose

Serviços:
- `gateway`: API Gateway Node.js
- `worker`: Workers Python (2+ réplicas)
- `minio`: Object Storage
- `kafka`: Message broker
- `zookeeper`: Coordenação Kafka
- `postgres`: TimescaleDB
- `redis`: Cache e rate limiting

### Variáveis de Ambiente

Todas as configurações via `.env`:
- URLs de conexão
- Chaves secretas
- Limites e timeouts
- Políticas de retenção

## 📝 Logging e Monitoramento

### Logging Estruturado

- **Formato**: JSON (produção) ou console (desenvolvimento)
- **Níveis**: DEBUG, INFO, WARNING, ERROR
- **Contexto**: Inclui user_id, request_id, claim_check, etc.

### Health Checks

- `/api/v1/health`: Health check básico
- `/api/v1/health/detailed`: Verifica dependências (Kafka, MinIO, TimescaleDB)

### Métricas

- **Kafka**: Lag do consumidor, throughput
- **MinIO**: Espaço usado, objetos por bucket
- **Workers**: Arquivos processados, erros
- **TimescaleDB**: Tamanho de chunks, status de continuous aggregates

## 📊 Volume de Dados

### Estimativas

- **Exemplo**: 1 dispositivo, 4 sensores = 4MB a cada 8 horas
- **Projeção**: 1000 dispositivos = ~500MB/hora = ~12GB/dia
- **Solução**: Claim Check Pattern + bulk inserts + limpeza automática

### Retenção

- **Kafka**: 7 dias (apenas Claim Checks)
- **MinIO**: 7 dias (arquivos completos)
- **TimescaleDB Dados Brutos**: 30 dias (configurável)
- **TimescaleDB Agregados**: Indefinidamente
- **Limpeza**: Automática (políticas configuradas)

## 🛠️ Tecnologias

- **Node.js**: Runtime para gateway
- **Fastify**: Framework web assíncrono
- **MinIO**: Object Storage (S3-compatible)
- **Kafka**: Message broker
- **Python**: Workers de processamento
- **TimescaleDB**: Banco de dados time-series
- **Redis**: Cache e rate limiting
- **SQLAlchemy**: ORM
- **Docker**: Containerização

## 📚 Próximos Passos

1. **Autenticação Real**: Integrar gateway com banco de dados
2. **Métricas Prometheus**: Exportar métricas
3. **Tracing**: OpenTelemetry para observabilidade
4. **Dead Letter Queue**: Para mensagens com erro persistente
5. **WebSockets**: Para notificações em tempo real
6. **Particionamento**: Tabela de telemetria particionada por mês
7. **MinIO Cluster**: Para alta disponibilidade

---

**Arquitetura v1.0.0 escalável e robusta para milhões de pontos de telemetria!** 🚀
