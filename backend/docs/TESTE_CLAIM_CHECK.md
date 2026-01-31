# 🧪 Teste do Claim Check Pattern

## Como Testar a Implementação

### 1. Iniciar Serviços

```bash
cd backend
docker-compose up -d

# Aguardar todos os serviços iniciarem
docker-compose ps
```

### 2. Verificar MinIO

```bash
# Acessar console
# http://localhost:9001
# Login: minioadmin / minioadmin

# Verificar bucket (deve existir automaticamente)
docker-compose exec minio mc ls minio/telemetry-raw
```

### 3. Obter Token de Autenticação

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Salvar token
export TOKEN="seu-token-aqui"
```

### 4. Enviar Telemetria

```bash
curl -X POST http://localhost:8000/api/v1/telemetry/bulk \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '[
    {
      "equip_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "equip_nome": "Freezer Teste",
      "equip_status": "ATIVO",
      "sensor": [
        {
          "sensor_uuid": "660e8400-e29b-41d4-a716-446655440001",
          "sensor_tipo": "temperatura",
          "sensor_nome": "Sensor Temperatura",
          "valor": 25.5,
          "timestamp": "2024-01-15T10:00:00Z",
          "sensor_datahora_coleta": "2024-01-15T10:00:00Z"
        }
      ]
    }
  ]'
```

**Resposta esperada:**
```json
{
  "status": "accepted",
  "received": 1,
  "message": "Dados recebidos e enviados para processamento",
  "claim_check": "telemetry/2024-01-15-10-30-00/uuid.json.gz"
}
```

### 5. Verificar Logs

#### Gateway

```bash
docker-compose logs gateway | grep -i "storage\|claim"
```

**Deve mostrar:**
- "Storage MinIO inicializado"
- "Telemetria salva em storage"
- "Claim Check enviado para Kafka"

#### Workers

```bash
docker-compose logs worker | grep -i "claim\|download\|processado"
```

**Deve mostrar:**
- "Processando Claim Check"
- "Arquivo baixado e descomprimido"
- "Telemetria processada"
- "Arquivo removido após processamento" (se configurado)

### 6. Verificar MinIO (Console Web)

1. Acessar `http://localhost:9001`
2. Login: `minioadmin` / `minioadmin`
3. Navegar para bucket `telemetry-raw`
4. Verificar estrutura: `telemetry/YYYY-MM-DD-HH-MM-SS/uuid.json.gz`
5. Verificar que arquivos são criados

### 7. Verificar Kafka

```bash
# Verificar mensagens no tópico
docker-compose exec kafka \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic telemetry.raw \
  --from-beginning \
  --max-messages 1
```

**Deve mostrar Claim Check (~1KB):**
```json
{
  "claim_check": "telemetry/2024-01-15-10-30-00/uuid.json.gz",
  "storage_type": "minio",
  "file_size": 1500000,
  ...
}
```

### 8. Verificar PostgreSQL

```bash
# Conectar ao banco
docker-compose exec postgres psql -U easysmart -d easysmart_db

# Verificar dados inseridos
SELECT COUNT(*) FROM telemetry_data;
SELECT * FROM telemetry_data ORDER BY created_at DESC LIMIT 10;
```

## ✅ Checklist de Verificação

- [ ] MinIO está rodando e acessível
- [ ] Gateway salva arquivos no MinIO
- [ ] Gateway envia Claim Check para Kafka
- [ ] Kafka recebe mensagens pequenas (~1KB)
- [ ] Workers consomem Claim Check
- [ ] Workers baixam arquivos do MinIO
- [ ] Workers processam e inserem no PostgreSQL
- [ ] Arquivos são removidos após processamento (se configurado)
- [ ] Dados aparecem no PostgreSQL

## 🐛 Troubleshooting

### Gateway não salva arquivos

```bash
# Verificar logs
docker-compose logs gateway | grep -i error

# Verificar conexão com MinIO
docker-compose exec gateway ping minio
```

### Workers não baixam arquivos

```bash
# Verificar logs
docker-compose logs worker | grep -i error

# Verificar conexão com MinIO
docker-compose exec worker ping minio

# Verificar credenciais
docker-compose exec worker env | grep MINIO
```

### Arquivos não aparecem no MinIO

```bash
# Verificar se bucket existe
docker-compose exec minio mc ls minio/

# Criar bucket manualmente se necessário
docker-compose exec minio mc mb minio/telemetry-raw
```

---

**Teste completo e verificação do Claim Check Pattern!** ✅
