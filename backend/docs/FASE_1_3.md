# Fase 1.3.0 — Backend Estável (Hotfixes e Governança)

Este documento resume as implementações consolidadas na versão **1.3.0** do backend.

## ✅ Entregas

- **Migrations mais resilientes** para bases existentes (correções em 007, 010, 017, 021, 022, 023).
- **Criação automática do banco** antes das migrations (`ensure_database.py`).
- **Swagger por domínio HTTPS** com URL pública configurável (`SWAGGER_SERVER_URL`).
- **Debug centralizado do PostgreSQL** no gateway (`POSTGRES_DEBUG`), com mascaramento de dados sensíveis.
- **Bootstrap master admin reforçado**, garantindo:
  - tenant sistema (id=0) com `plan_code` e timestamps
  - organization/workspace do sistema (id=0)
  - usuário admin com timestamps e campos obrigatórios
- **Governança self-service no tenant**:
  - validação de limites por plano ao criar users/orgs/workspaces
  - endpoints de dashboard (limits/usage/alerts)
- **Compose/config lendo variáveis do `.env`**, incluindo `POSTGRES_*` e `MASTER_ADMIN_*`.
- **Logs do PostgreSQL no container** via `POSTGRES_LOG_STATEMENT` e `POSTGRES_LOG_DURATION`.

## 🧱 Migrations adicionadas/corrigidas

- `021_fix_usertype_enum`: corrige enum `usertype`
- `022_user_type_default_frontend`: garante `user_type` default `frontend`
- `023_fix_userstatus_enum`: corrige enum `userstatus`

## ⚙️ Variáveis novas/ajustadas

- `SWAGGER_SERVER_URL`: URL pública do Swagger atrás de proxy HTTPS
- `POSTGRES_DEBUG`: log de queries/retorno no gateway (com redaction)
- `POSTGRES_LOG_STATEMENT`: nível de log no Postgres (`none|ddl|mod|all`)
- `POSTGRES_LOG_DURATION`: loga duração das queries (`on|off`)
- `MASTER_ADMIN_*`: passadas para o gateway via compose

## 🔗 Endpoints adicionados (tenant)

- `GET /api/v1/tenant/limits`
- `GET /api/v1/tenant/usage/daily`
- `GET /api/v1/tenant/alerts/history`

## 📝 Observações

- A autenticação continua usando **hash bcrypt** (não comparar senha no SQL).
- O Swagger agora envia **Authorization** quando o `security` global está definido.
- Para proxy reverso, é necessário repassar o header `Authorization`.

