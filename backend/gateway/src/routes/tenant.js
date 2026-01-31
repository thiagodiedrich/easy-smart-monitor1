/**
 * Rotas de Administração do Tenant (self-service)
 */
import { queryDatabase } from '../utils/database.js';
import { logger } from '../utils/logger.js';
import bcrypt from 'bcrypt';

function isTenantAdmin(request) {
  const role = request.user?.role;
  return role === 'admin' || role === 'manager';
}

function normalizeScopeArray(value) {
  if (value === undefined || value === null) {
    return [0];
  }
  if (Array.isArray(value)) {
    const parsed = value.map((v) => parseInt(v, 10)).filter((v) => !Number.isNaN(v));
    if (parsed.includes(0) || parsed.length === 0) {
      return [0];
    }
    return parsed;
  }
  const parsed = parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed === 0) {
    return [0];
  }
  return [parsed];
}

async function validateOrgWorkspace(tenantId, organizationIds, workspaceIds) {
  if (!organizationIds.includes(0)) {
    const orgs = await queryDatabase(
      `SELECT id FROM organizations WHERE tenant_id = $1 AND id = ANY($2)`,
      [tenantId, organizationIds]
    );
    if (orgs.length !== organizationIds.length) {
      return { ok: false, error: 'organization_id inválido para o tenant' };
    }
  }
  if (!workspaceIds.includes(0)) {
    const workspaces = await queryDatabase(
      `
        SELECT w.id
        FROM workspaces w
        INNER JOIN organizations o ON w.organization_id = o.id
        WHERE o.tenant_id = $1 AND w.id = ANY($2)
      `,
      [tenantId, workspaceIds]
    );
    if (workspaces.length !== workspaceIds.length) {
      return { ok: false, error: 'workspace_id inválido para o tenant' };
    }
  }
  return { ok: true };
}

async function auditLog(request, action, targetType, targetId, metadata = {}) {
  try {
    await queryDatabase(
      `
        INSERT INTO audit_logs (
          tenant_id,
          actor_user_id,
          actor_role,
          action,
          target_type,
          target_id,
          metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      `,
      [
        request.user?.tenant_id ?? null,
        request.user?.user_id ?? null,
        request.user?.role ?? null,
        action,
        targetType,
        targetId ? String(targetId) : null,
        metadata,
      ]
    );
  } catch (error) {
    logger.warn('Falha ao registrar audit log', { error: error.message });
  }
}

export const tenantRoutes = async (fastify) => {
  // Middleware de autenticação + admin tenant
  fastify.addHook('onRequest', async (request, reply) => {
    try {
      await request.jwtVerify();
      if (Number(request.user?.tenant_id) === 0 || !isTenantAdmin(request)) {
        return reply.code(403).send({
          error: 'FORBIDDEN',
          message: 'Acesso restrito ao admin do tenant',
        });
      }
    } catch (err) {
      return reply.code(401).send({
        error: 'UNAUTHORIZED',
        message: 'Não autorizado',
      });
    }
  });

  // Organizations
  fastify.post('/organizations', async (request, reply) => {
    const { name } = request.body || {};
    if (!name) {
      return reply.code(400).send({ error: 'name é obrigatório' });
    }
    const result = await queryDatabase(
      `
        INSERT INTO organizations (tenant_id, name, created_at, updated_at)
        VALUES ($1, $2, NOW(), NOW())
        RETURNING id
      `,
      [request.user.tenant_id, name]
    );
    await auditLog(request, 'create', 'organization', result[0]?.id, { name });
    return reply.code(201).send({ id: result[0]?.id });
  });

  fastify.get('/organizations', async (request, reply) => {
    const result = await queryDatabase(
      `SELECT * FROM organizations WHERE tenant_id = $1 ORDER BY id ASC`,
      [request.user.tenant_id]
    );
    return reply.send(result);
  });

  fastify.put('/organizations/:id', async (request, reply) => {
    const { id } = request.params;
    const { name } = request.body || {};
    await queryDatabase(
      `
        UPDATE organizations
        SET name = COALESCE($1, name), updated_at = NOW()
        WHERE id = $2 AND tenant_id = $3
      `,
      [name || null, id, request.user.tenant_id]
    );
    await auditLog(request, 'update', 'organization', id, { name });
    return reply.send({ status: 'ok' });
  });

  fastify.delete('/organizations/:id', async (request, reply) => {
    const { id } = request.params;
    await queryDatabase(
      `DELETE FROM organizations WHERE id = $1 AND tenant_id = $2`,
      [id, request.user.tenant_id]
    );
    await auditLog(request, 'delete', 'organization', id, {});
    return reply.send({ status: 'ok' });
  });

  // Workspaces
  fastify.post('/workspaces', async (request, reply) => {
    const { organization_id, name } = request.body || {};
    if (!organization_id || !name) {
      return reply.code(400).send({ error: 'organization_id e name são obrigatórios' });
    }
    const org = await queryDatabase(
      `SELECT id FROM organizations WHERE id = $1 AND tenant_id = $2`,
      [organization_id, request.user.tenant_id]
    );
    if (!org || org.length === 0) {
      return reply.code(404).send({ error: 'Organization não encontrada' });
    }
    const result = await queryDatabase(
      `
        INSERT INTO workspaces (organization_id, name, created_at, updated_at)
        VALUES ($1, $2, NOW(), NOW())
        RETURNING id
      `,
      [organization_id, name]
    );
    await auditLog(request, 'create', 'workspace', result[0]?.id, { name, organization_id });
    return reply.code(201).send({ id: result[0]?.id });
  });

  fastify.get('/workspaces', async (request, reply) => {
    const result = await queryDatabase(
      `
        SELECT w.*
        FROM workspaces w
        INNER JOIN organizations o ON w.organization_id = o.id
        WHERE o.tenant_id = $1
        ORDER BY w.id ASC
      `,
      [request.user.tenant_id]
    );
    return reply.send(result);
  });

  fastify.put('/workspaces/:id', async (request, reply) => {
    const { id } = request.params;
    const { name } = request.body || {};
    await queryDatabase(
      `
        UPDATE workspaces
        SET name = COALESCE($1, name), updated_at = NOW()
        WHERE id = $2 AND organization_id IN (
          SELECT id FROM organizations WHERE tenant_id = $3
        )
      `,
      [name || null, id, request.user.tenant_id]
    );
    await auditLog(request, 'update', 'workspace', id, { name });
    return reply.send({ status: 'ok' });
  });

  fastify.delete('/workspaces/:id', async (request, reply) => {
    const { id } = request.params;
    await queryDatabase(
      `
        DELETE FROM workspaces
        WHERE id = $1 AND organization_id IN (
          SELECT id FROM organizations WHERE tenant_id = $2
        )
      `,
      [id, request.user.tenant_id]
    );
    await auditLog(request, 'delete', 'workspace', id, {});
    return reply.send({ status: 'ok' });
  });

  // Alert rules
  fastify.post('/alerts', async (request, reply) => {
    const { organization_id = 0, workspace_ids = [0], threshold_percent = 80, enabled = true } = request.body || {};
    const result = await queryDatabase(
      `
        INSERT INTO tenant_alert_rules (tenant_id, organization_id, workspace_ids, threshold_percent, enabled, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        RETURNING id
      `,
      [request.user.tenant_id, organization_id, workspace_ids, threshold_percent, enabled]
    );
    await auditLog(request, 'create', 'alert_rule', result[0]?.id, { organization_id, workspace_ids, threshold_percent });
    return reply.code(201).send({ id: result[0]?.id });
  });

  fastify.get('/alerts', async (request, reply) => {
    const result = await queryDatabase(
      `SELECT * FROM tenant_alert_rules WHERE tenant_id = $1 ORDER BY id ASC`,
      [request.user.tenant_id]
    );
    return reply.send(result);
  });

  fastify.put('/alerts/:id', async (request, reply) => {
    const { id } = request.params;
    const payload = request.body || {};
    await queryDatabase(
      `
        UPDATE tenant_alert_rules
        SET
          organization_id = COALESCE($1, organization_id),
          workspace_ids = COALESCE($2, workspace_ids),
          threshold_percent = COALESCE($3, threshold_percent),
          enabled = COALESCE($4, enabled),
          updated_at = NOW()
        WHERE id = $5 AND tenant_id = $6
      `,
      [payload.organization_id, payload.workspace_ids, payload.threshold_percent, payload.enabled, id, request.user.tenant_id]
    );
    await auditLog(request, 'update', 'alert_rule', id, payload);
    return reply.send({ status: 'ok' });
  });

  fastify.delete('/alerts/:id', async (request, reply) => {
    const { id } = request.params;
    await queryDatabase(
      `DELETE FROM tenant_alert_rules WHERE id = $1 AND tenant_id = $2`,
      [id, request.user.tenant_id]
    );
    await auditLog(request, 'delete', 'alert_rule', id, {});
    return reply.send({ status: 'ok' });
  });

  // Webhooks
  fastify.post('/webhooks', async (request, reply) => {
    const { organization_id = 0, workspace_ids = [0], event_types = ['quota_80','quota_90','quota_100'], url, secret, enabled = false } = request.body || {};
    const result = await queryDatabase(
      `
        INSERT INTO tenant_webhooks (tenant_id, organization_id, workspace_ids, event_types, url, secret, enabled, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
        RETURNING id
      `,
      [request.user.tenant_id, organization_id, workspace_ids, event_types, url || null, secret || null, enabled]
    );
    await auditLog(request, 'create', 'webhook', result[0]?.id, { organization_id, workspace_ids, event_types, url });
    return reply.code(201).send({ id: result[0]?.id });
  });

  fastify.get('/webhooks', async (request, reply) => {
    const result = await queryDatabase(
      `SELECT * FROM tenant_webhooks WHERE tenant_id = $1 ORDER BY id ASC`,
      [request.user.tenant_id]
    );
    return reply.send(result);
  });

  fastify.put('/webhooks/:id', async (request, reply) => {
    const { id } = request.params;
    const payload = request.body || {};
    await queryDatabase(
      `
        UPDATE tenant_webhooks
        SET
          organization_id = COALESCE($1, organization_id),
          workspace_ids = COALESCE($2, workspace_ids),
          event_types = COALESCE($3, event_types),
          url = COALESCE($4, url),
          secret = COALESCE($5, secret),
          enabled = COALESCE($6, enabled),
          updated_at = NOW()
        WHERE id = $7 AND tenant_id = $8
      `,
      [
        payload.organization_id,
        payload.workspace_ids,
        payload.event_types,
        payload.url,
        payload.secret,
        payload.enabled,
        id,
        request.user.tenant_id,
      ]
    );
    await auditLog(request, 'update', 'webhook', id, payload);
    return reply.send({ status: 'ok' });
  });

  fastify.delete('/webhooks/:id', async (request, reply) => {
    const { id } = request.params;
    await queryDatabase(
      `DELETE FROM tenant_webhooks WHERE id = $1 AND tenant_id = $2`,
      [id, request.user.tenant_id]
    );
    await auditLog(request, 'delete', 'webhook', id, {});
    return reply.send({ status: 'ok' });
  });

  // Users (Tenant)
  fastify.post('/users', async (request, reply) => {
    const {
      username,
      email,
      password,
      role = 'viewer',
      status = 'active',
      organization_id,
      workspace_id,
    } = request.body || {};

    if (!username || !password) {
      return reply.code(400).send({ error: 'username e password são obrigatórios' });
    }

    const orgIds = normalizeScopeArray(organization_id);
    const wsIds = normalizeScopeArray(workspace_id);
    const scopeCheck = await validateOrgWorkspace(request.user.tenant_id, orgIds, wsIds);
    if (!scopeCheck.ok) {
      return reply.code(400).send({ error: scopeCheck.error });
    }

    const hashed = await bcrypt.hash(password, 10);
    const result = await queryDatabase(
      `
        INSERT INTO users (
          username, email, hashed_password,
          tenant_id, organization_id, workspace_id,
          role, user_type, status,
          created_at, updated_at
        ) VALUES (
          $1, $2, $3,
          $4, $5, $6,
          $7, 'frontend', $8,
          NOW(), NOW()
        )
        RETURNING id
      `,
      [username, email || null, hashed, request.user.tenant_id, orgIds, wsIds, role, status]
    );
    await auditLog(request, 'create', 'user', result[0]?.id, { username, role, status });
    return reply.code(201).send({ id: result[0]?.id });
  });

  fastify.get('/users', async (request, reply) => {
    const result = await queryDatabase(
      `
        SELECT id, username, email, role, status, user_type, organization_id, workspace_id, created_at, updated_at
        FROM users
        WHERE tenant_id = $1
        ORDER BY id ASC
      `,
      [request.user.tenant_id]
    );
    return reply.send(result);
  });

  fastify.put('/users/:id', async (request, reply) => {
    const { id } = request.params;
    const {
      email,
      role,
      status,
      organization_id,
      workspace_id,
    } = request.body || {};

    const orgIds = normalizeScopeArray(organization_id);
    const wsIds = normalizeScopeArray(workspace_id);
    const scopeCheck = await validateOrgWorkspace(request.user.tenant_id, orgIds, wsIds);
    if (!scopeCheck.ok) {
      return reply.code(400).send({ error: scopeCheck.error });
    }

    await queryDatabase(
      `
        UPDATE users
        SET
          email = COALESCE($1, email),
          role = COALESCE($2, role),
          status = COALESCE($3, status),
          organization_id = COALESCE($4, organization_id),
          workspace_id = COALESCE($5, workspace_id),
          updated_at = NOW()
        WHERE id = $6 AND tenant_id = $7
      `,
      [email || null, role || null, status || null, orgIds, wsIds, id, request.user.tenant_id]
    );
    await auditLog(request, 'update', 'user', id, { email, role, status });
    return reply.send({ status: 'ok' });
  });

  fastify.patch('/users/:id/password', async (request, reply) => {
    const { id } = request.params;
    const { password } = request.body || {};
    if (!password) {
      return reply.code(400).send({ error: 'password é obrigatório' });
    }
    const hashed = await bcrypt.hash(password, 10);
    await queryDatabase(
      `UPDATE users SET hashed_password = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3`,
      [hashed, id, request.user.tenant_id]
    );
    await auditLog(request, 'update_password', 'user', id, {});
    return reply.send({ status: 'ok' });
  });

  fastify.delete('/users/:id', async (request, reply) => {
    const { id } = request.params;
    await queryDatabase(
      `DELETE FROM users WHERE id = $1 AND tenant_id = $2`,
      [id, request.user.tenant_id]
    );
    await auditLog(request, 'delete', 'user', id, {});
    return reply.send({ status: 'ok' });
  });
};
