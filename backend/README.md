# Easy Smart Monitor - Backend API v1.3.0

**Versão estável:** 1.3.0

API RESTful escalável para recebimento e processamento de dados de telemetria do Easy Smart Monitor.

## 🎯 Versão 1.3.0 Estável

Esta é a versão estável do backend (código e documentação alinhados à v1.3.0), implementando:
- ✅ **Claim Check Pattern** para payloads grandes
- ✅ **TimescaleDB Continuous Aggregates** para consultas otimizadas
- ✅ **Arquitetura distribuída** (Node.js Gateway + Kafka + Python Workers)
- ✅ **Object Storage** (MinIO) para Data Lake
- ✅ **Endpoints Analytics** otimizados para dashboards e Home Assistant
- ✅ **Multi-tenant SaaS** (tenant, organization, workspace)
- ✅ **Quotas e Billing** (planos, limites, uso diário)
- ✅ **Alertas e Webhooks** (thresholds 80/90/100)
- ✅ **Admin Master global** (tenant_id=0)

## 🏗️ Arquitetura

### Componentes Principais

- **Node.js Gateway (Fastify)**: Recebe requisições HTTP e salva arquivos em Object Storage
- **MinIO (Object Storage)**: Armazena arquivos de telemetria (Data Lake)
- **Apache Kafka**: Streaming de Claim Checks (referências ~1KB)
- **Python Workers**: Baixam arquivos e processam telemetria
- **TimescaleDB**: Banco de dados com Continuous Aggregates
- **Redis**: Cache e rate limiting

### Fluxo de Dados (Claim Check Pattern)

```
Cliente (Home Assistant)
    ↓ HTTP POST (GZIP comprimido ~1-10MB)
Node.js Gateway (Fastify)
    ↓ Valida JWT, Rate Limit
    ↓ Salva arquivo em MinIO (streaming)
    ↓ Gera Claim Check (referência ~1KB)
Kafka (apenas referência ~1KB)
    ↓ Consumer
Python Workers
    ↓ Lê Claim Check
    ↓ Baixa arquivo do MinIO
    ↓ Processa e insere no TimescaleDB
    ↓ Remove arquivo (opcional)
TimescaleDB
    ↓ Continuous Aggregates (automático)
    ↓ Queries otimizadas (milissegundos)
```

## 📊 Volume de Dados

- **Exemplo**: 1 dispositivo com 4 sensores = 4MB a cada 8 horas
- **Com GZIP**: ~1-2MB comprimido
- **Lotes típicos**: 10-50 dispositivos = 10-100MB por lote
- **Solução**: Claim Check Pattern permite qualquer tamanho

## 🚀 Início Rápido

### Pré-requisitos

- Docker e Docker Compose
- 8GB RAM mínimo (recomendado 12GB)
- 50GB espaço em disco

### Executar com Docker Compose

```bash
cd backend

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas configurações

# Iniciar serviços
docker-compose up -d

# Verificar status
docker-compose ps
```

A API estará disponível em: `http://localhost:8000`

MinIO Console: `http://localhost:9001` (minioadmin/minioadmin)

### Configurar TimescaleDB

Após iniciar os serviços, execute as migrations (o script agora garante o banco antes de criar tabelas):

```bash
# Opção 1: container temporário (funciona mesmo se o worker estiver reiniciando)
docker compose run --rm worker python run_migrations.py upgrade

# Opção 2: dentro do container do worker (se estiver estável)
docker compose exec worker python run_migrations.py upgrade
```

### Testar a API

#### 1. Acessar Documentação Swagger

Abra no navegador: `http://localhost:8000/api/v1/docs`

A documentação Swagger permite testar todos os endpoints diretamente no navegador.

#### 2. Obter Token de Autenticação

**Para Frontend/Dashboard:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**Para Dispositivo IoT:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/device/login \
  -H "Content-Type: application/json" \
  -d '{"username":"device_user","password":"device_pass"}'
```

#### 3. Enviar Telemetria (requer token device)

```bash
curl -X POST http://localhost:8000/api/v1/telemetry/bulk \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <device_token>" \
  -d '[{
    "equip_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "equip_nome": "Freezer Teste",
    "sensor": [{
      "sensor_uuid": "660e8400-e29b-41d4-a716-446655440001",
      "sensor_tipo": "temperatura",
      "valor": 25.5,
      "timestamp": "2024-01-15T10:00:00Z"
    }]
  }]'
```

#### 4. Consultar Histórico (requer token frontend)

```bash
curl -X GET \
  "http://localhost:8000/api/v1/analytics/equipment/550e8400-e29b-41d4-a716-446655440000/history?period=hour" \
  -H "Authorization: Bearer <frontend_token>"
```

## 📁 Estrutura do Projeto

```
backend/
├── gateway/                 # Node.js Gateway (Fastify)
│   ├── src/
│   │   ├── routes/         # Rotas da API
│   │   │   ├── auth.js     # Autenticação
│   │   │   ├── telemetry.js # Telemetria (Claim Check)
│   │   │   ├── analytics.js # Analytics (Continuous Aggregates)
│   │   │   └── health.js   # Health checks
│   │   ├── kafka/          # Produtor Kafka (Claim Check)
│   │   ├── storage/        # Storage Service (MinIO)
│   │   ├── utils/          # Utilitários (database, logger)
│   │   └── app.js          # Aplicação Fastify
│   ├── package.json
│   └── Dockerfile
│
├── workers-python/          # Python Workers
│   ├── app/
│   │   ├── consumers/      # Consumidores Kafka
│   │   ├── processors/     # Processadores de telemetria
│   │   ├── storage/        # Cliente Storage (download)
│   │   ├── models/         # Modelos SQLAlchemy
│   │   ├── migrations/     # Migrations TimescaleDB (001 a 015)
│   │   └── core/           # Configurações
│   ├── requirements.txt
│   ├── Dockerfile
│   └── run_migrations.py   # Script de migrations
│
├── docker-compose.yml       # Orquestração de serviços
├── VERSION                  # Versão do backend (1.3.0)
├── README.md                # Este arquivo
├── docs/                    # Documentação detalhada
│   ├── API_ANALYTICS.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   ├── FASES_1_2.md
│   ├── INSTALACAO_AAPANEL.md
│   ├── SECURITY.md
│   ├── TIMESCALEDB_SETUP.md
│   └── ...
└── CHANGELOG.md             # Histórico de versões
```

## 📚 Documentação da API

### Swagger/OpenAPI

A documentação interativa da API está disponível em:

**URL**: `http://localhost:8000/api/v1/docs`

A documentação Swagger permite:
- ✅ Visualizar todos os endpoints disponíveis
- ✅ Testar requisições diretamente no navegador
- ✅ Ver schemas de requisição e resposta
- ✅ Autenticar e testar endpoints protegidos

### Documentação Completa

Para documentação detalhada dos endpoints, consulte:
- **docs/API_ANALYTICS.md**: Endpoints de analytics otimizados
- **docs/SECURITY.md**: Detalhes de segurança e autenticação
- **docs/FASES_1_2.md**: Fases da evolução multi-tenant (1.2.x)

## 🔐 Autenticação

A API utiliza JWT tokens com dois tipos de usuários:

### Tipos de Usuário

1. **Frontend/Dashboard** (`user_type: 'frontend'`)
   - Acesso: Analytics, dashboards, relatórios
   - Login: `POST /api/v1/auth/login`

2. **Device/IoT** (`user_type: 'device'`)
   - Acesso: Envio de telemetria
   - Login: `POST /api/v1/auth/device/login`

### Endpoints de Autenticação

1. **Login Frontend**: `POST /api/v1/auth/login`
2. **Login Device**: `POST /api/v1/auth/device/login`
3. **Refresh Token**: `POST /api/v1/auth/refresh`
4. **Telemetria**: `POST /api/v1/telemetry/bulk` (requer token device)
5. **Analytics**: `GET /api/v1/analytics/*` (requer token frontend)

## 📈 Endpoints Principais

### Autenticação

- `POST /api/v1/auth/login` - Login para frontend/dashboard
- `POST /api/v1/auth/device/login` - Login para dispositivos IoT
- `POST /api/v1/auth/refresh` - Renovar token de acesso

### Telemetria

- `POST /api/v1/telemetry/bulk` - Recebe lotes de telemetria (salva em storage, envia Claim Check)
- `POST /api/v1/telemetria/bulk` - Compatibilidade (mesmo endpoint)

**Requer**: Token JWT do tipo `device`

### Analytics (Otimizados com Continuous Aggregates)

- `GET /api/v1/analytics/equipment/:uuid/history` - Histórico de equipamento
- `GET /api/v1/analytics/sensor/:uuid/history` - Histórico de sensor
- `GET /api/v1/analytics/equipment/:uuid/stats` - Estatísticas agregadas
- `GET /api/v1/analytics/home-assistant/:uuid` - Dados para Home Assistant

**Requer**: Token JWT do tipo `frontend`

### Health Checks

- `GET /api/v1/health` - Health check básico da API
- `GET /api/v1/health/detailed` - Health check detalhado (Kafka, Redis, MinIO, TimescaleDB)

**Não requer**: Autenticação

## 🗄️ Object Storage (MinIO)

### Bucket

- **Nome**: `telemetry-raw`
- **Estrutura**: `telemetry/YYYY-MM-DD-HH-MM-SS/uuid.json.gz`
- **Retenção**: 7 dias (configurável)
- **Compressão**: GZIP (70-85% de redução)

### Acesso

- **API**: `http://localhost:9000`
- **Console**: `http://localhost:9001`
- **Credenciais padrão**: minioadmin/minioadmin

## 📊 TimescaleDB Continuous Aggregates

### Agregações Automáticas

- **Horária** (`telemetry_hourly`): Para dashboards e análises recentes
- **Diária** (`telemetry_daily`): Para análises históricas e tendências

### Performance

- **Queries analíticas**: 100-2000x mais rápidas (milissegundos)
- **Refresh automático**: Horária (30 min), Diária (2 horas)
- **Retenção**: Dados brutos 30 dias, agregados indefinidamente

## 🔄 Processamento Assíncrono

Dados são processados de forma assíncrona:

1. Gateway recebe e valida
2. Salva arquivo em MinIO (streaming)
3. Envia Claim Check para Kafka (não bloqueia)
4. Responde imediatamente ao cliente
5. Workers processam em background
6. Workers baixam arquivo do storage
7. Processam e inserem no TimescaleDB
8. Continuous Aggregates atualizam automaticamente
9. Removem arquivo após processamento (opcional)

## 📊 Monitoramento

- **Health Checks**: `/api/v1/health` e `/api/v1/health/detailed`
- **Logs**: Estruturados em JSON
- **Kafka**: Métricas via comandos Kafka
- **MinIO**: Console web em `http://localhost:9001`
- **TimescaleDB**: Queries otimizadas com Continuous Aggregates

## 🔒 Segurança

- Rate limiting por IP e usuário
- Validação rigorosa de dados
- JWT tokens com expiração curta
- HTTPS obrigatório em produção
- Sanitização de inputs
- Todas as regras de negócio centralizadas na API

## 📝 Licença

Proprietário - Datacase

## 📋 Histórico de Versões (Changelog)

### [1.3.0] - 2024-02-09 - Estável Atualizada

**Melhorias e Correções:**
- ✅ **Migrations mais resilientes** (007, 010, 017, 021, 022, 023) em bases existentes
- ✅ **Criação automática do banco** antes das migrations
- ✅ **Swagger por domínio HTTPS** (URL pública configurável)
- ✅ **Debug centralizado do PostgreSQL** (query + retorno mascarado)
- ✅ **Bootstrap master admin** reforçado (tenant/org/workspace sistema)
- ✅ **Dashboards de governança** (limits/usage/alerts no tenant)
- ✅ **Compose/config** lendo `POSTGRES_*` e `MASTER_ADMIN_*` do `.env`

**Funcionalidades Mantidas:**
- Arquitetura Distribuída (Node.js Gateway + Kafka + Python Workers)
- Claim Check Pattern
- TimescaleDB Continuous Aggregates
- Endpoints Analytics Otimizados
- Health Checks

### [1.0.0] - 2024-01-15 - Versão Estável Inicial

**Funcionalidades Principais:**
- ✅ **Arquitetura Distribuída**: Node.js Gateway + Kafka + Python Workers
- ✅ **Claim Check Pattern**: Object Storage (MinIO) + Kafka para payloads grandes
- ✅ **TimescaleDB Continuous Aggregates**: Agregações horárias e diárias automáticas
- ✅ **Endpoints Analytics**: Consultas otimizadas para dashboards e Home Assistant
- ✅ **Autenticação JWT**: Tokens com refresh e separação por tipo de usuário
- ✅ **Rate Limiting**: Por IP e usuário usando Redis
- ✅ **Health Checks**: Básico e detalhado

**Performance:**
- Throughput Gateway: 10,000+ requisições/segundo
- Latência Gateway: 10-50ms (p95)
- Throughput Kafka: 100,000+ mensagens/segundo
- Queries Analytics: 10-50ms (100-2000x mais rápido)

---

Para o changelog completo e detalhado, consulte: **CHANGELOG.md**

## 📚 Documentação Adicional

- **Swagger/OpenAPI**: `http://localhost:8000/api/v1/docs` (Documentação interativa)
- **docs/ARCHITECTURE.md**: Detalhes técnicos da arquitetura
- **docs/DEPLOYMENT.md**: Guia completo de deploy e configuração
- **docs/FASES_1_2.md**: Histórico de fases 1.2.0 → 1.2.7
- **docs/INSTALACAO_AAPANEL.md**: Instalação e configuração no aaPanel
- **docs/TIMESCALEDB_SETUP.md**: Setup e configuração do TimescaleDB
- **docs/API_ANALYTICS.md**: Documentação detalhada dos endpoints de analytics
- **docs/SECURITY.md**: Detalhes de segurança e Defense in Depth
- **CHANGELOG.md**: Histórico completo e detalhado de versões
- **VERSION**: Arquivo com a versão atual do backend (1.3.0)

## 🆘 Suporte

Para problemas ou dúvidas:
- Verificar logs: `docker-compose logs`
- Consultar documentação: Arquivos `.md` na pasta `backend/docs`
- Health checks: `/api/v1/health/detailed`
- MinIO Console: `http://localhost:9001`

---

**Backend v1.3.0 estável - Pronto para produção!** 🚀
