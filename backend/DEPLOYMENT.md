# Guia de Deploy - Easy Smart Monitor Backend v1.0.0

## 🚀 Deploy com Docker Compose

### Pré-requisitos

- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM mínimo (recomendado 12GB)
- 50GB espaço em disco

### Passos para Deploy

1. **Clonar/Configurar o Projeto**

```bash
cd backend
cp .env.example .env
# Editar .env com suas configurações
```

2. **Configurar Variáveis de Ambiente**

Edite o arquivo `.env` e configure:
- `SECRET_KEY`: Gere uma chave secreta forte (mínimo 32 caracteres)
- `POSTGRES_PASSWORD`: Senha do TimescaleDB
- `MINIO_ROOT_USER`: Usuário do MinIO (padrão: minioadmin)
- `MINIO_ROOT_PASSWORD`: Senha do MinIO (padrão: minioadmin)
- `VALID_USERS`: Usuários para desenvolvimento (JSON)
- Outras configurações conforme necessário

3. **Iniciar Serviços**

```bash
docker-compose up -d
```

4. **Verificar Status**

```bash
docker-compose ps
```

Todos os serviços devem estar "healthy" ou "running".

5. **Configurar TimescaleDB**

Após iniciar os serviços, execute as migrations:

```bash
# Entrar no container do worker
docker-compose exec worker bash

# Executar migrations
cd /app
python run_migrations.py upgrade
```

As migrations irão:
- Criar extensão TimescaleDB
- Converter `telemetry_data` em hypertable
- Criar continuous aggregates (horária e diária)
- Configurar políticas de refresh e retenção

6. **Acessar MinIO Console**

- URL: `http://localhost:9001`
- Usuário: `minioadmin` (ou o configurado)
- Senha: `minioadmin` (ou o configurado)

7. **Verificar Logs**

```bash
# Gateway
docker-compose logs -f gateway

# Workers
docker-compose logs -f worker

# Kafka
docker-compose logs -f kafka

# MinIO
docker-compose logs -f minio

# TimescaleDB
docker-compose logs -f postgres
```

A API estará disponível em: `http://localhost:8000`

## 🔧 Configuração de Produção

### Variáveis de Ambiente Críticas

```env
# Segurança
SECRET_KEY=<gerar-chave-forte-32-chars>
POSTGRES_PASSWORD=<senha-forte>
NODE_ENV=production
MINIO_ROOT_USER=<usuario-forte>
MINIO_ROOT_PASSWORD=<senha-forte>

# Kafka
KAFKA_BROKERS=kafka:9092
KAFKA_TOPIC=telemetry.raw

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=${MINIO_ROOT_USER}
MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD}
MINIO_BUCKET=telemetry-raw
STORAGE_TYPE=minio

# TimescaleDB
DATABASE_URL=postgresql+asyncpg://easysmart:password@postgres:5432/easysmart_db
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=20

# Redis
REDIS_URL=redis://redis:6379/0

# Rate Limiting
RATE_LIMIT_PER_MINUTE=1000
MAX_BULK_SIZE=10000

# Storage
DELETE_FILE_AFTER_PROCESSING=true
FILE_RETENTION_DAYS=7

# TimescaleDB Continuous Aggregates
# (Configurado via migrations)
```

### Recomendações de Produção

1. **HTTPS**: Use um proxy reverso (Nginx/Traefik) com SSL
2. **Backup**: Configure backups automáticos do TimescaleDB e MinIO
3. **Monitoramento**: Configure logs centralizados e alertas
4. **Escalabilidade**: Use múltiplas instâncias da API com load balancer
5. **Segurança**: Revise todas as variáveis de ambiente
6. **Autenticação**: Integre gateway com banco de dados (remover VALID_USERS)
7. **MinIO**: Configure cluster mode para alta disponibilidade
8. **TimescaleDB**: Configure read replicas para consultas analytics

## 📊 Monitoramento

### Health Checks

```bash
# Health check básico
curl http://localhost:8000/api/v1/health

# Health check detalhado
curl http://localhost:8000/api/v1/health/detailed
```

### Logs

```bash
# Ver logs da API
docker-compose logs -f gateway

# Ver logs do worker
docker-compose logs -f worker

# Ver logs do TimescaleDB
docker-compose logs -f postgres

# Ver logs do Kafka
docker-compose logs -f kafka

# Ver logs do MinIO
docker-compose logs -f minio
```

### Métricas Kafka

```bash
# Listar tópicos
docker-compose exec kafka \
  kafka-topics --list --bootstrap-server localhost:9092

# Verificar consumidores
docker-compose exec kafka \
  kafka-consumer-groups --bootstrap-server localhost:9092 --list

# Verificar lag do consumidor
docker-compose exec kafka \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group telemetry-workers
```

### Métricas MinIO

- **Console Web**: `http://localhost:9001`
- **API**: `http://localhost:9000`
- **Comandos**: `mc` (MinIO Client)

### Métricas TimescaleDB

```bash
# Conectar ao banco
docker-compose exec postgres psql -U easysmart -d easysmart_db

# Verificar hypertable
SELECT * FROM timescaledb_information.hypertables;

# Verificar continuous aggregates
SELECT * FROM timescaledb_information.continuous_aggregates;

# Verificar políticas
SELECT * FROM timescaledb_information.jobs;

# Verificar status das políticas
SELECT * FROM timescaledb_information.job_stats;
```

## 🔄 Manutenção

### Atualizar Código

```bash
# Parar serviços
docker-compose down

# Atualizar código
git pull

# Reconstruir imagens
docker-compose build

# Iniciar serviços
docker-compose up -d

# Executar migrations (se houver novas)
docker-compose exec worker python run_migrations.py upgrade
```

### Backup do Banco de Dados

```bash
# Backup
docker-compose exec postgres pg_dump -U easysmart easysmart_db > backup.sql

# Restore
docker-compose exec -T postgres psql -U easysmart easysmart_db < backup.sql
```

### Backup do MinIO

```bash
# Usar MinIO Client (mc)
docker-compose exec minio mc mirror /data /backup
```

### Escalar Workers

```bash
# Escalar para 4 workers
docker-compose up -d --scale worker=4
```

### Limpeza de Arquivos Antigos

Os arquivos são limpos automaticamente pelo worker de limpeza baseado em `FILE_RETENTION_DAYS`.

Para executar manualmente:

```bash
docker-compose exec worker python -m app.workers.cleanup_worker
```

### Atualizar Continuous Aggregates Manualmente

```bash
# Conectar ao banco
docker-compose exec postgres psql -U easysmart -d easysmart_db

# Forçar refresh de uma agregação
CALL refresh_continuous_aggregate('telemetry_hourly', NULL, NULL);
CALL refresh_continuous_aggregate('telemetry_daily', NULL, NULL);
```

## 🐛 Troubleshooting

### API não inicia

1. Verificar logs: `docker-compose logs gateway`
2. Verificar se Kafka está rodando: `docker-compose ps kafka`
3. Verificar se MinIO está rodando: `docker-compose ps minio`
4. Verificar se TimescaleDB está rodando: `docker-compose ps postgres`
5. Verificar variáveis de ambiente: `docker-compose config`

### Erro de conexão com banco

1. Verificar `DATABASE_URL` no `.env`
2. Verificar se TimescaleDB está acessível
3. Verificar credenciais
4. Verificar se migrations foram executadas

### Workers não processam

1. Verificar logs: `docker-compose logs worker`
2. Verificar conexão com Kafka
3. Verificar conexão com MinIO
4. Verificar conexão com TimescaleDB
5. Verificar lag do consumidor

### MinIO não conecta

1. Verificar se MinIO está rodando: `docker-compose ps minio`
2. Verificar logs: `docker-compose logs minio`
3. Verificar variáveis de ambiente do MinIO
4. Acessar console: `http://localhost:9001`

### Arquivos não são baixados

1. Verificar se arquivo existe no MinIO (console web)
2. Verificar permissões do bucket
3. Verificar credenciais do MinIO
4. Verificar logs do worker

### Continuous Aggregates não atualizam

1. Verificar se migrations foram executadas
2. Verificar status das políticas: `SELECT * FROM timescaledb_information.jobs;`
3. Verificar logs do TimescaleDB
4. Forçar refresh manual se necessário

### Queries Analytics lentas

1. Verificar se continuous aggregates existem
2. Verificar se estão sendo atualizados
3. Verificar índices: `\d+ telemetry_hourly`
4. Verificar se está usando a view correta (não a tabela bruta)

### Rate limiting muito restritivo

Ajustar em `.env`:
- `RATE_LIMIT_PER_MINUTE`
- `RATE_LIMIT_PER_HOUR`

### Performance lenta

1. Aumentar `DATABASE_POOL_SIZE`
2. Verificar índices do banco
3. Aumentar número de workers
4. Verificar lag do Kafka
5. Verificar espaço em disco do MinIO
6. Verificar se continuous aggregates estão funcionando

## 📈 Escalabilidade

### Horizontal Scaling

Para escalar horizontalmente:

1. **Gateway**: Múltiplas instâncias atrás de load balancer
2. **Workers**: Aumentar `--scale worker=N`
3. **Kafka**: Configurar cluster mode
4. **MinIO**: Configurar cluster mode
5. **Database**: Configurar read replicas

### Exemplo com Nginx

```nginx
upstream api_backend {
    server gateway1:8000;
    server gateway2:8000;
    server gateway3:8000;
}

server {
    listen 80;
    server_name api.easysmart.local;
    
    location / {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 🔒 Segurança

### Checklist de Segurança

- [ ] `SECRET_KEY` forte e único
- [ ] `POSTGRES_PASSWORD` forte
- [ ] `MINIO_ROOT_PASSWORD` forte
- [ ] `NODE_ENV=production`
- [ ] HTTPS configurado
- [ ] CORS configurado corretamente
- [ ] Rate limiting ativo
- [ ] Senhas de banco fortes
- [ ] Backups configurados
- [ ] Logs de segurança monitorados
- [ ] Firewall configurado
- [ ] Atualizações de segurança aplicadas
- [ ] Remover `VALID_USERS` (usar banco de dados)
- [ ] MinIO com acesso restrito (não expor porta 9000/9001 publicamente)
- [ ] TimescaleDB com acesso restrito

## 📞 Suporte

Para problemas ou dúvidas:
- Verificar logs: `docker-compose logs`
- Consultar documentação: `ARCHITECTURE.md`, `TIMESCALEDB_SETUP.md`, `API_ANALYTICS.md`
- Health checks: `/api/v1/health/detailed`
- MinIO Console: `http://localhost:9001`
- TimescaleDB: Conectar via `psql` e verificar status

---

**Backend v1.0.0 pronto para produção com Claim Check Pattern e Continuous Aggregates!** 🚀
