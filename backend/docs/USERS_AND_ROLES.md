% USERS_AND_ROLES.md
# Tipos de Usuários e Permissões

Este documento descreve como funcionam **tipos de usuário**, **roles** e **escopo** no backend.

## 1) Tipos de usuário (`user_type`)

### `frontend`
- Usuário do **dashboard/backoffice**.
- Autenticação em `POST /api/v1/auth/login`.
- Pode acessar APIs de administração e gestão do tenant, conforme as permissões.
- Recebe `permissions` no `GET /api/v1/auth/me` para controle de UI e ações.

### `device`
- Usuário de **dispositivo IoT** (ingestão de telemetria).
- Autenticação em `POST /api/v1/auth/device/login`.
- **Acesso restrito** às rotas:
  - `POST /api/v1/auth/device/login`
  - `POST /api/v1/auth/refresh`
  - `GET /api/v1/auth/me`
  - `POST /api/v1/telemetry/bulk` (e `/api/v1/telemetria/bulk`)
  - `GET /api/v1/tenant/workspaces` (somente leitura)
- Deve possuir **escopo fixo**: `tenant_id`, **1** `organization_id` e **1** `workspace_id`.

## 2) Roles e permissões (`role`)

O campo `role` é **JSONB** e determina as permissões do usuário.  
O backend deriva um conjunto de permissões e aplica tanto na API quanto no frontend.

### Roles padrão
- `viewer`: leitura de recursos do tenant.
- `manager`: leitura e gestão de recursos do tenant **exceto organizations** (não cria/edita organizations).
- `admin`: controle total do tenant.
- `super`: reservado ao **super admin global**.

## 3) Super Admin global

- **Único no sistema**, controlado por `is_superadmin = true`.
- Também possui `role = [0]`.
- Pode acessar **todos os tenants** e **todas as APIs**.
- Criado via bootstrap com variáveis `MASTER_ADMIN_*` no `.env`.

## 4) Escopo por token (JWT)

Todo token contém o escopo do usuário:
- `tenant_id`
- `organization_id`
- `workspace_id`

**Regra principal:** a API **sempre valida o escopo pelo token**.  
Filtros enviados pelo cliente **nunca** substituem o escopo do token.

Regras adicionais:
- **super user (`role [0]`)** pode atuar em qualquer tenant, organization e workspace, desde que informe o escopo correto.
- **admin/manager** podem atuar apenas nos `tenant_id`, `organization_id` e `workspace_id` que estiverem no escopo do token.

## 5) Permissões retornadas no `/auth/me`

O endpoint `GET /api/v1/auth/me` retorna:
- `permissions`: lista efetiva de permissões
- `role` e `user_type`
- `tenant_id`, `organization_id`, `workspace_id`

O frontend usa essas permissões para:
- exibir ou ocultar menus
- habilitar ou bloquear botões e formulários
- prevenir ações fora do escopo

## 6) Mapa completo de permissões por role

### `super`
- `*`

### `admin`
- `tenant.*`
- `analytics.*`
- `telemetry.*`
- `health.*`
- `auth.*`
- `admin.*`

### `manager`
- `tenant.organizations.read`
- `tenant.workspaces.*`
- `tenant.equipments.*`
- `tenant.sensors.*`
- `tenant.alerts.*`
- `tenant.webhooks.*`
- `tenant.limits.read`
- `tenant.usage.read`
- `tenant.alerts.history.read`
- `tenant.users.read`
- `tenant.users.create`
- `tenant.users.update`
- `tenant.users.password`
- `tenant.users.status`
- `analytics.*`
- `health.*`
- `auth.me`

### `viewer`
- `tenant.organizations.read`
- `tenant.workspaces.read`
- `tenant.equipments.read`
- `tenant.sensors.read`
- `tenant.alerts.read`
- `tenant.webhooks.read`
- `tenant.limits.read`
- `tenant.usage.read`
- `tenant.alerts.history.read`
- `tenant.users.read`
- `analytics.*`
- `health.*`
- `auth.me`

### `device`
- `auth.device.login`
- `auth.refresh`
- `auth.me`
- `telemetry.bulk`
- `tenant.workspaces.read`

