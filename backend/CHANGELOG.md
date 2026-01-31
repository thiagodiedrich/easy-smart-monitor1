# Changelog - Easy Smart Monitor Backend

Todas as mudanças notáveis do backend estão documentadas neste arquivo.  
**Versão estável atual:** 1.3.0

---

## [1.3.0] - 2024-02-09 - Estável Atualizada

### ✨ Entregas
- ✅ Criação automática do banco antes das migrations
- ✅ Correções em migrations (007, 010, 017, 021, 022, 023) para ambientes existentes
- ✅ Swagger por domínio HTTPS (URL pública configurável)
- ✅ Debug centralizado do PostgreSQL (query + retorno mascarado)
- ✅ Bootstrap master admin reforçado (tenant/org/workspace sistema)
- ✅ Dashboard de governança (limits, usage, alerts por tenant)
- ✅ Compose/config lendo `POSTGRES_*` e `MASTER_ADMIN_*` do `.env`
- ✅ Docs atualizados para o fluxo `run_migrations.py upgrade`

### 📝 Migrations (1.3.0)
- **007_tenant_id_users_equipments**: fallback quando `equipments.user_id` não existe
- **010_plans_and_limits**: defaults `0` para limites nulos
- **017_equipments_sensors_telemetry_refactor**: cast de `status` para `text` no `lower()`
- **021_fix_usertype_enum**: corrige enum `usertype`
- **022_user_type_default_frontend**: default `frontend` em `user_type`
- **023_fix_userstatus_enum**: corrige enum `userstatus`

### 🧰 Utilitários
- **workers-python/ensure_database.py**: garante o banco antes das migrations

---

## [1.2.7] - 2024-02-08 - SaaS Multi-Tenant (Fase 7)

### ✨ Entregas
- ✅ Alertas globais e por tenant/org/workspace (80/90/100)
- ✅ Webhooks com escopo global e por tenant
- ✅ Worker de alertas + cron configurável
- ✅ Uso diário por org/workspace (tabela scoped)
- ✅ Atraso de alertas por plano/tenant

### 📝 Migrations (1.2.7)
- **013_tenant_usage_daily_scoped**: uso diário por org/workspace
- **014_alerting_tables**: regras, alertas, webhooks e delivery
- **015_alert_delay_seconds**: atraso por plano/tenant

### 📚 Documentação
- **docs/FASES_1_2.md**: resumo completo das fases 1.2.x

---

## [1.2.6] - 2024-02-07 - SaaS Multi-Tenant (Fase 6)

### ✨ Entregas
- ✅ Bootstrap de usuário master (tenant_id=0)
- ✅ Suporte a organization_id/workspace_id em users
- ✅ Admin global com escopo total (tenant_id=0)

### 📝 Migrations (1.2.6)
- **012_org_workspace_in_users**: org/workspace em users

---

## [1.2.5] - 2024-02-06 - SaaS Multi-Tenant (Fase 5)

### ✨ Entregas
- ✅ Planos e limites por tenant
- ✅ Enforcement de quotas na ingestão
- ✅ Preparação para billing real

### 📝 Migrations (1.2.5)
- **010_plans_and_limits**: planos e limites por tenant

---

## [1.2.4] - 2024-02-05 - SaaS Multi-Tenant (Fase 4)

### ✨ Entregas
- ✅ Uso diário por tenant (billing-ready)
- ✅ Metadados de ingestão (itens/sensores/bytes)

### 📝 Migrations (1.2.4)
- **009_tenant_usage_daily**: uso diário por tenant

---

## [1.2.3] - 2024-02-04 - SaaS Multi-Tenant (Fase 3)

### ✨ Entregas
- ✅ Isolamento por tenant/org/workspace em analytics
- ✅ Rate limit por tenant

---

## [1.2.2] - 2024-02-03 - SaaS Multi-Tenant (Fase 2)

### ✨ Entregas
- ✅ organization_id e workspace_id em equipments
- ✅ Propagação de contexto na ingestão (Kafka)

### 📝 Migrations (1.2.2)
- **008_org_workspace_in_equipments**: org/workspace em equipments

---

## [1.2.1] - 2024-02-02 - SaaS Multi-Tenant (Fase 1)

### ✨ Entregas
- ✅ tenant_id em users/equipments
- ✅ JWT com tenant_id
- ✅ Backfill para tenant legado

### 📝 Migrations (1.2.1)
- **007_tenant_id_users_equipments**: tenant_id em users/equipments

---

## [1.2.0] - 2024-02-01 - SaaS Multi-Tenant (Fase 0)

### ✨ Entregas
- ✅ Tabelas SaaS base (tenants, organizations, workspaces)
- ✅ Contexto multi-tenant opcional (Gateway/Workers)

### 📝 Migrations (1.2.0)
- **006_tenant_organization_workspace**: base multi-tenant

---

## [1.1.0] - 2024-01-15 - Versão Estável

### 🎯 Versão Estável de Produção

Esta é a versão estável 1.1.0 do backend Easy Smart Monitor. O código da pasta `backend/` e a documentação (README, CHANGELOG, VERSION e demais .md) estão alinhados a esta versão.

### ✨ Melhorias e Correções

- ✅ **Segurança Aprimorada**: Defense in Depth implementado
  - Autenticação separada para dispositivos e frontend
  - Gerenciamento de status de usuários (Ativo, Inativo, Bloqueado, Temporariamente Bloqueado)
  - **Migration 005_user_security_fields**: enums UserType e UserStatus, campos de tentativas de login, bloqueio temporário e metadados de segurança na tabela `users`
  - Penalty Box com backoff exponencial
  - Prevenção de uploads concorrentes
  - Blacklist em Redis
  - Logging estruturado para Fail2Ban

- ✅ **Limpeza de Código**: Remoção de imports não utilizados
- ✅ **Correção Docker Compose**: Volumes duplicados e incorretos corrigidos
- ✅ **Documentação Atualizada**: README, CHANGELOG, VERSION e todos os .md alinhados à v1.1.0
- ✅ **Swagger/OpenAPI**: Documentação interativa adicionada em `/api/v1/docs`

### 📝 Migrations (1.1.0)

- **005_user_security_fields**: Campos de segurança do usuário (enums UserType e UserStatus, tentativas de login, bloqueio temporário, metadados na tabela `users`)

### 📊 Funcionalidades Mantidas

Todas as funcionalidades da versão 1.0.0 foram mantidas e aprimoradas:
- ✅ Arquitetura Distribuída (Node.js Gateway + Kafka + Python Workers)
- ✅ Claim Check Pattern
- ✅ TimescaleDB Continuous Aggregates
- ✅ Endpoints Analytics Otimizados
- ✅ Health Checks

---

## [1.0.0] - 2024-01-15 - Versão Estável Inicial

### 🎯 Versão Estável de Produção

Esta é a primeira versão estável do backend Easy Smart Monitor, implementando arquitetura completa e otimizada para processamento de telemetria em larga escala.

### ✨ Funcionalidades Principais

#### Arquitetura Distribuída
- ✅ **Node.js Gateway (Fastify)**: API Gateway de alta performance
- ✅ **Apache Kafka**: Message broker para processamento assíncrono
- ✅ **Python Workers**: Processadores de telemetria escaláveis
- ✅ **TimescaleDB**: Banco de dados otimizado para time-series
- ✅ **MinIO**: Object Storage para Data Lake
- ✅ **Redis**: Cache e rate limiting

#### Claim Check Pattern
- ✅ **Object Storage**: Armazenamento de arquivos grandes (MinIO)
- ✅ **Claim Check**: Referências pequenas (~1KB) no Kafka
- ✅ **Streaming**: Upload/download sem consumir memória excessiva
- ✅ **Reprocessamento**: Fácil reprocessar arquivos do storage
- ✅ **Limpeza Automática**: Remoção automática de arquivos antigos

#### TimescaleDB Continuous Aggregates
- ✅ **Hypertable**: Tabela `telemetry_data` convertida em hypertable
- ✅ **Agregação Horária**: `telemetry_hourly` para dashboards
- ✅ **Agregação Diária**: `telemetry_daily` para análises históricas
- ✅ **Refresh Automático**: Políticas configuradas (30 min / 2 horas)
- ✅ **Retenção Automática**: Dados brutos 30 dias, agregados indefinidamente
- ✅ **Real-Time Aggregation**: Combina dados materializados com dados brutos

#### Endpoints API
- ✅ **Autenticação**: JWT tokens com refresh
- ✅ **Telemetria**: Recebimento de lotes (Claim Check Pattern)
- ✅ **Analytics**: Consultas otimizadas (Continuous Aggregates)
  - Histórico de equipamento
  - Histórico de sensor
  - Estatísticas agregadas
  - Dados para Home Assistant
- ✅ **Health Checks**: Básico e detalhado

#### Segurança
- ✅ **JWT Authentication**: Tokens com expiração curta
- ✅ **Rate Limiting**: Por IP e usuário (Redis)
- ✅ **Validação**: Rigorosa de dados e parâmetros
- ✅ **Sanitização**: Inputs sanitizados (prepared statements)
- ✅ **Centralização**: Todas as regras de negócio na API

### 📊 Performance

- **Throughput Gateway**: 10,000+ requisições/segundo
- **Latência Gateway**: 10-50ms (p95)
- **Throughput Kafka**: 100,000+ mensagens/segundo
- **Throughput Workers**: 1,000-2,000 arquivos/segundo por worker
- **Queries Analytics**: 10-50ms (100-2000x mais rápido que sem Continuous Aggregates)

### 🔧 Componentes Técnicos

#### Gateway Node.js
- Fastify framework
- MinIO client (Object Storage)
- KafkaJS (produtor Kafka)
- ioredis (rate limiting)
- pg (PostgreSQL client para analytics)
- JWT authentication

#### Workers Python
- kafka-python (consumidor)
- minio (cliente MinIO)
- orjson (JSON rápido)
- SQLAlchemy (async ORM)
- asyncpg (PostgreSQL driver)
- structlog (logging estruturado)

#### Infraestrutura
- Docker Compose para orquestração
- TimescaleDB (PostgreSQL com extensão)
- MinIO (Object Storage)
- Apache Kafka + Zookeeper
- Redis

### 📝 Migrations

- **001_base_tables**: Cria tabelas base (users, equipments, sensors, telemetry_data)
- **002_timescaledb_hypertable**: Cria hypertable
- **003_continuous_aggregates**: Cria continuous aggregates
- **004_continuous_aggregates_policies**: Configura políticas

### 📚 Documentação

- ✅ **README.md**: Visão geral e início rápido
- ✅ **ARCHITECTURE.md**: Arquitetura detalhada
- ✅ **DEPLOYMENT.md**: Guia completo de deploy
- ✅ **TIMESCALEDB_SETUP.md**: Setup TimescaleDB
- ✅ **API_ANALYTICS.md**: Documentação endpoints analytics
- ✅ **CHANGELOG.md**: Este arquivo

### 🐛 Correções

- Nenhuma (versão inicial estável)

### 🔄 Melhorias Futuras

- Autenticação integrada com banco de dados
- Métricas Prometheus
- Tracing OpenTelemetry
- Dead Letter Queue
- WebSockets para notificações
- MinIO Cluster mode
- TimescaleDB Read replicas

---

**Versão 1.1.0 Estável - Código e documentação alinhados. Pronta para Produção!** 🚀
