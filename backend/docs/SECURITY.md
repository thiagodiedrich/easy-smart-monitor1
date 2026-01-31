# Segurança - Defense in Depth v1.1.0

## 🛡️ Arquitetura de Segurança

Implementação de **Defense in Depth** com 3 camadas de proteção:

```
┌─────────────────────────────────────┐
│  Camada 1: Firewall/WAF (Fail2Ban)  │ ← Bloqueio de rede
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Camada 2: Blacklist Redis          │ ← Verificação ultra-rápida
│  (onRequest Hook)                   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Camada 3: Shield Plugin            │ ← Lógica de negócio
│  - Rate Limiting                    │
│  - Penalty Box                      │
│  - Concurrency Lock                 │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Camada 4: Autenticação (JWT)       │ ← Validação de identidade
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Camada 5: Autorização (RBAC)        │ ← Validação de permissões
└─────────────────────────────────────┘
```

## 🔐 Autenticação Separada

### Dois Tipos de Usuários

1. **Frontend** (`user_type = 'frontend'`)
   - Para dashboard e integrações web
   - Login: `POST /api/v1/auth/login`
   - Rate Limit: 100 req/min (normal), 200 req/min (jail)

2. **Device** (`user_type = 'device'`)
   - Para dispositivos IoT (Home Assistant, etc.)
   - Login: `POST /api/v1/auth/device/login`
   - Rate Limit: 10 req/min (normal), 30 req/min (jail)

### Regras de Segurança

- ✅ Usuário `frontend` **NÃO** pode fazer login em `/device/login`
- ✅ Usuário `device` **NÃO** pode fazer login em `/login`
- ✅ Apenas `device` pode enviar telemetria
- ✅ Status do usuário: `active`, `inactive`, `blocked`

## 🚨 Status de Usuário

### Active (Ativo)
- Pode fazer login normalmente
- Status padrão ao criar usuário

### Inactive (Inativo)
- **NÃO** pode fazer login
- Mensagem: "Usuário inativo. Contate o administrador."

### Blocked (Bloqueado)
- **NÃO** pode fazer login
- Mensagem: "Usuário bloqueado. Contate o administrador."

### Locked (Bloqueado Temporariamente)
- Bloqueado após 5 tentativas falhadas
- Duração: 30 minutos
- Mensagem: "Usuário bloqueado temporariamente até [data]"

## 🛡️ Shield Plugin - Defense in Depth

### Camada 1: Blacklist Redis

Verificação ultra-rápida antes de qualquer processamento:

```javascript
// Verifica IP e Device ID na blacklist
if (isBanned) {
  return 403 Forbidden
}
```

### Camada 2: Rate Limiting Inteligente

#### Limites por Tipo de Usuário

| Tipo | Normal | Jail | Banimento |
|------|--------|------|-----------|
| Device | 10/min | 30/min | 15min → 1h → 24h → 7d |
| Frontend | 100/min | 200/min | 15min → 1h → 24h → 7d |

#### Penalty Box (Backoff Exponencial)

- **1ª violação**: 15 minutos
- **2ª violação**: 1 hora
- **3ª violação**: 24 horas
- **4ª+ violação**: 7 dias

### Camada 3: Prevenção de Concorrência

Lock distribuído no Redis para evitar múltiplas conexões simultâneas:

```javascript
// Apenas 1 upload por vez por dispositivo
if (lockExists) {
  return 409 Conflict
}
```

## 📊 Endpoints de Autenticação

### Frontend Login

```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "senha123"
}
```

**Resposta:**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Device Login

```bash
POST /api/v1/auth/device/login
Content-Type: application/json

{
  "username": "device_001",
  "password": "senha123",
  "device_id": "home-assistant-001"  // Opcional
}
```

**Resposta:**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Refresh Token

```bash
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
```

## 🔒 Proteções Implementadas

### 1. Rate Limiting por Tipo
- Limites diferentes para device e frontend
- Headers informativos: `X-RateLimit-*`

### 2. Penalty Box
- Banimento progressivo (backoff exponencial)
- Contador de violações persistente

### 3. Blacklist Redis
- Verificação antes de qualquer processamento
- IP e Device ID bloqueados

### 4. Prevenção de Concorrência
- Lock distribuído para uploads
- Evita múltiplas conexões simultâneas

### 5. Validação de Status
- Verifica status antes de permitir login
- Mensagens claras de erro

### 6. Controle de Tentativas
- Bloqueio após 5 tentativas falhadas
- Duração: 30 minutos

## 📝 Logging Estruturado

Logs formatados para Fail2Ban:

```json
{
  "level": "warn",
  "msg": "[SECURITY] Ban IP",
  "ip": "192.168.1.50",
  "deviceId": "device_001",
  "banTime": 3600,
  "reason": "rate_limit_exceeded",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🔧 Configuração Fail2Ban

### jail.local

```ini
[node-api-protection]
enabled = true
port    = 80,443
filter  = node-api-security
logpath = /var/log/myapp/app.log
maxretry = 5
bantime  = 3600
findtime = 600
action   = iptables-allports
```

### filter (node-api-security.conf)

```ini
[Definition]
failregex = ^.*\[SECURITY\] Ban IP.*"ip":"<HOST>".*$
ignoreregex =
```

## 🚀 Como Usar

### 1. Executar Migration

```bash
cd backend/workers-python
python run_migrations.py upgrade
```

### 2. Criar Usuário Device

```sql
INSERT INTO users (username, hashed_password, user_type, status)
VALUES (
  'device_001',
  '$2b$10$...',  -- Hash bcrypt da senha
  'device',
  'active'
);
```

### 3. Criar Usuário Frontend

```sql
INSERT INTO users (username, hashed_password, user_type, status)
VALUES (
  'admin',
  '$2b$10$...',  -- Hash bcrypt da senha
  'frontend',
  'active'
);
```

### 4. Testar Autenticação

```bash
# Login Device
curl -X POST http://localhost:8000/api/v1/auth/device/login \
  -H "Content-Type: application/json" \
  -d '{"username":"device_001","password":"senha123"}'

# Login Frontend
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"senha123"}'
```

## 📊 Monitoramento

### Verificar Entidades Banidas

```bash
# Via API (se implementado endpoint admin)
GET /api/v1/admin/security/banned
```

### Verificar Rate Limits

Headers de resposta:
- `X-RateLimit-Limit`: Limite máximo
- `X-RateLimit-Remaining`: Requisições restantes
- `X-RateLimit-Reset`: Timestamp de reset

## ⚠️ Melhorias Futuras

- [ ] Whitelist de IPs confiáveis
- [ ] Device fingerprinting avançado
- [ ] Rate limiting adaptativo
- [ ] Token revocation list
- [ ] Geolocation blocking
- [ ] Métricas Prometheus

---

**Segurança Defense in Depth implementada!** 🛡️
