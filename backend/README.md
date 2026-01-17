# Easy Smart Monitor - Backend API v1.0.0

API RESTful escalável para recebimento e processamento de dados de telemetria do Easy Smart Monitor.

## 🎯 Versão 1.0.0 Estável

Esta é a versão estável do backend, implementando:
- ✅ **Claim Check Pattern** para payloads grandes
- ✅ **TimescaleDB Continuous Aggregates** para consultas otimizadas
- ✅ **Arquitetura distribuída** (Node.js Gateway + Kafka + Python Workers)
- ✅ **Object Storage** (MinIO) para Data Lake
- ✅ **Endpoints Analytics** otimizados para dashboards e Home Assistant

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

Após iniciar os serviços, execute as migrations:

```bash
# Entrar no container do worker
docker-compose exec worker bash

# Executar migrations
cd /app
python run_migrations.py upgrade
```

### Testar a API

```bash
# 1. Obter token de autenticação
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 2. Enviar telemetria (com token)
curl -X POST http://localhost:8000/api/v1/telemetry/bulk \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
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

# 3. Consultar histórico (otimizado)
curl -X GET \
  "http://localhost:8000/api/v1/analytics/equipment/550e8400-e29b-41d4-a716-446655440000/history?period=hour" \
  -H "Authorization: Bearer <token>"
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
│   │   ├── migrations/     # Migrations TimescaleDB
│   │   └── core/           # Configurações
│   ├── requirements.txt
│   ├── Dockerfile
│   └── run_migrations.py   # Script de migrations
│
├── docker-compose.yml       # Orquestração de serviços
├── README.md               # Este arquivo
├── ARCHITECTURE.md         # Detalhes da arquitetura
├── DEPLOYMENT.md           # Guia de deploy
├── TIMESCALEDB_SETUP.md    # Setup TimescaleDB
├── API_ANALYTICS.md        # Documentação endpoints analytics
└── CHANGELOG.md            # Histórico de versões
```

## 🔐 Autenticação

A API utiliza OAuth2 com JWT tokens:

1. **Login**: `POST /api/v1/auth/login`
2. **Refresh Token**: `POST /api/v1/auth/refresh`
3. **Telemetria**: `POST /api/v1/telemetry/bulk` (requer Bearer token)
4. **Analytics**: `GET /api/v1/analytics/*` (requer Bearer token)

## 📈 Endpoints Principais

### Telemetria

- `POST /api/v1/telemetry/bulk` - Recebe lotes de telemetria (salva em storage, envia Claim Check)
- `POST /api/v1/telemetria/bulk` - Compatibilidade (mesmo endpoint)

### Analytics (Otimizados com Continuous Aggregates)

- `GET /api/v1/analytics/equipment/:uuid/history` - Histórico de equipamento
- `GET /api/v1/analytics/sensor/:uuid/history` - Histórico de sensor
- `GET /api/v1/analytics/equipment/:uuid/stats` - Estatísticas agregadas
- `GET /api/v1/analytics/home-assistant/:uuid` - Dados para Home Assistant

### Health Checks

- `GET /api/v1/health` - Health check da API
- `GET /api/v1/health/detailed` - Health check detalhado

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

## 📚 Documentação Adicional

- **ARCHITECTURE.md**: Detalhes técnicos da arquitetura
- **DEPLOYMENT.md**: Guia completo de deploy e configuração
- **TIMESCALEDB_SETUP.md**: Setup e configuração do TimescaleDB
- **API_ANALYTICS.md**: Documentação dos endpoints de analytics
- **CHANGELOG.md**: Histórico de versões

## 🆘 Suporte

Para problemas ou dúvidas:
- Verificar logs: `docker-compose logs`
- Consultar documentação: Arquivos `.md` na pasta `backend/`
- Health checks: `/api/v1/health/detailed`
- MinIO Console: `http://localhost:9001`

---

**Backend v1.0.0 estável - Pronto para produção!** 🚀
