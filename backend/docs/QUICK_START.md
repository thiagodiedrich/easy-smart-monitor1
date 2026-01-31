# 🚀 Quick Start - Claim Check Pattern

## Início Rápido

### 1. Configurar

```bash
cd backend
cp .env.example .env
# Editar .env se necessário
```

### 2. Iniciar

```bash
docker-compose up -d
```

### 3. Verificar

```bash
# Status dos serviços
docker-compose ps

# Health check
curl http://localhost:8000/api/v1/health

# MinIO Console
# http://localhost:9001 (minioadmin/minioadmin)
```

### 4. Testar

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

# Enviar telemetria
curl -X POST http://localhost:8000/api/v1/telemetry/bulk \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
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

### 5. Verificar Processamento

```bash
# Logs do gateway (deve mostrar "Telemetria salva em storage")
docker-compose logs -f gateway

# Logs do worker (deve mostrar "Processando Claim Check")
docker-compose logs -f worker

# Verificar arquivos no MinIO (console web)
# http://localhost:9001 → Buckets → telemetry-raw
```

## 📊 O Que Acontece

1. **Gateway recebe** dados (1-10MB)
2. **Gateway salva** em MinIO (comprimido GZIP)
3. **Gateway envia** Claim Check para Kafka (~1KB)
4. **Gateway responde** 202 Accepted (imediato)
5. **Worker consome** Claim Check do Kafka
6. **Worker baixa** arquivo do MinIO
7. **Worker processa** e insere no PostgreSQL
8. **Worker remove** arquivo (opcional)

## ✅ Verificação

- ✅ Gateway: `docker-compose logs gateway | grep "salva em storage"`
- ✅ Worker: `docker-compose logs worker | grep "Claim Check"`
- ✅ MinIO: Console web mostra arquivos
- ✅ Kafka: Mensagens pequenas (~1KB)

---

**Tudo funcionando!** 🎉
