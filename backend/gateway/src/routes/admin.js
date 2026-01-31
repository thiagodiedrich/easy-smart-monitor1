/**
 * Rotas Admin Globais (tenant_id=0)
 */
import { queryDatabase } from '../utils/database.js';
import { logger } from '../utils/logger.js';

function isSystemAdmin(request) {
  const tenantId = request.user?.tenant_id;
  const role = request.user?.role;
  return Number(tenantId) === 0 && role === 'admin';
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

export const adminRoutes = async (fastify) => {
  // Middleware de autenticação + admin global
  fastify.addHook('onRequest', async (request, reply) => {
    try {
      await request.jwtVerify();
      if (!isSystemAdmin(request)) {
        return reply.code(403).send({
          error: 'FORBIDDEN',
          message: 'Acesso restrito ao admin global',
        });
      }
    } catch (err) {
      return reply.code(401).send({
        error: 'UNAUTHORIZED',
        message: 'Não autorizado',
      });
    }
  });

  // Tenants
  fastify.post('/tenants', async (request, reply) => {
    const { name, slug, status = 'active', plan_code, is_white_label = false } = request.body || {};
    if (!name || !slug) {
      return reply.code(400).send({ error: 'name e slug são obrigatórios' });
    }
    const result = await queryDatabase(
      `
        INSERT INTO tenants (name, slug, status, plan_code, is_white_label, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        RETURNING id
      `,
      [name, slug, status, plan_code || null, !!is_white_label]
    );
    await auditLog(request, 'create', 'tenant', result[0]?.id, { name, slug });
    return reply.code(201).send({ id: result[0]?.id });
  });

  fastify.get('/tenants', async (_request, reply) => {
    const result = await queryDatabase(`SELECT * FROM tenants ORDER BY id ASC`);
    return reply.send(result);
  });

  fastify.get('/tenants/:id', async (request, reply) => {
    const { id } = request.params;
    const result = await queryDatabase(`SELECT * FROM tenants WHERE id = $1`, [id]);
    if (!result || result.length === 0) {
      return reply.code(404).send({ error: 'Tenant não encontrado' });
    }
    return reply.send(result[0]);
  });

  fastify.put('/tenants/:id', async (request, reply) => {
    const { id } = request.params;
    const { name, slug, status, plan_code, is_white_label } = request.body || {};
    await queryDatabase(
      `
        UPDATE tenants
        SET
          name = COALESCE($1, name),
          slug = COALESCE($2, slug),
          status = COALESCE($3, status),
          plan_code = COALESCE($4, plan_code),
          is_white_label = COALESCE($5, is_white_label),
          updated_at = NOW()
        WHERE id = $6
      `,
      [name || null, slug || null, status || null, plan_code || null, is_white_label, id]
    );
    await auditLog(request, 'update', 'tenant', id, { name, slug, status, plan_code, is_white_label });
    return reply.send({ status: 'ok' });
  });

  fastify.patch('/tenants/:id/status', async (request, reply) => {
    const { id } = request.params;
    const { status } = request.body || {};
    if (!status) {
      return reply.code(400).send({ error: 'status é obrigatório' });
    }
    await queryDatabase(
      `UPDATE tenants SET status = $1, updated_at = NOW() WHERE id = $2`,
      [status, id]
    );
    await auditLog(request, 'update_status', 'tenant', id, { status });
    return reply.send({ status: 'ok' });
  });

  // Plans
  fastify.post('/plans', async (request, reply) => {
    const {
      code,
      name,
      status = 'active',
      items_per_day = 0,
      sensors_per_day = 0,
      bytes_per_day = 0,
      equipments_total = 0,
      sensors_total = 0,
      users_total = 0,
      organization_total = 0,
      workspace_total = 0,
      collection_interval = 60,
      alert_delay_seconds = 1,
    } = request.body || {};
    if (!code || !name) {
      return reply.code(400).send({ error: 'code e name são obrigatórios' });
    }
    await queryDatabase(
      `
        INSERT INTO plans (
          code, name, status,
          items_per_day, sensors_per_day, bytes_per_day,
          equipments_total, sensors_total, users_total,
          organization_total, workspace_total,
          collection_interval, alert_delay_seconds,
          created_at, updated_at
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW()
        )
      `,
      [
        code, name, status,
        items_per_day, sensors_per_day, bytes_per_day,
        equipments_total, sensors_total, users_total,
        organization_total, workspace_total,
        collection_interval, alert_delay_seconds,
      ]
    );
    await auditLog(request, 'create', 'plan', code, { name, status });
    return reply.code(201).send({ status: 'ok' });
  });

  fastify.get('/plans', async (_request, reply) => {
    const result = await queryDatabase(`SELECT * FROM plans ORDER BY code ASC`);
    return reply.send(result);
  });

  fastify.put('/plans/:code', async (request, reply) => {
    const { code } = request.params;
    const payload = request.body || {};
    await queryDatabase(
      `
        UPDATE plans
        SET
          name = COALESCE($1, name),
          status = COALESCE($2, status),
          items_per_day = COALESCE($3, items_per_day),
          sensors_per_day = COALESCE($4, sensors_per_day),
          bytes_per_day = COALESCE($5, bytes_per_day),
          equipments_total = COALESCE($6, equipments_total),
          sensors_total = COALESCE($7, sensors_total),
          users_total = COALESCE($8, users_total),
          organization_total = COALESCE($9, organization_total),
          workspace_total = COALESCE($10, workspace_total),
          collection_interval = COALESCE($11, collection_interval),
          alert_delay_seconds = COALESCE($12, alert_delay_seconds),
          updated_at = NOW()
        WHERE code = $13
      `,
      [
        payload.name || null,
        payload.status || null,
        payload.items_per_day,
        payload.sensors_per_day,
        payload.bytes_per_day,
        payload.equipments_total,
        payload.sensors_total,
        payload.users_total,
        payload.organization_total,
        payload.workspace_total,
        payload.collection_interval,
        payload.alert_delay_seconds,
        code,
      ]
    );
    await auditLog(request, 'update', 'plan', code, payload);
    return reply.send({ status: 'ok' });
  });

  fastify.patch('/plans/:code/status', async (request, reply) => {
    const { code } = request.params;
    const { status } = request.body || {};
    if (!status) {
      return reply.code(400).send({ error: 'status é obrigatório' });
    }
    await queryDatabase(
      `UPDATE plans SET status = $1, updated_at = NOW() WHERE code = $2`,
      [status, code]
    );
    await auditLog(request, 'update_status', 'plan', code, { status });
    return reply.send({ status: 'ok' });
  });

  // Tenant limits
  fastify.post('/tenants/:id/limits', async (request, reply) => {
    const { id } = request.params;
    const payload = request.body || {};
    await queryDatabase(
      `
        INSERT INTO tenant_limits (
          tenant_id,
          items_per_day, sensors_per_day, bytes_per_day,
          equipments_total, sensors_total, users_total,
          organization_total, workspace_total,
          collection_interval, alert_delay_seconds,
          created_at, updated_at
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW()
        )
        ON CONFLICT (tenant_id) DO UPDATE SET
          items_per_day = EXCLUDED.items_per_day,
          sensors_per_day = EXCLUDED.sensors_per_day,
          bytes_per_day = EXCLUDED.bytes_per_day,
          equipments_total = EXCLUDED.equipments_total,
          sensors_total = EXCLUDED.sensors_total,
          users_total = EXCLUDED.users_total,
          organization_total = EXCLUDED.organization_total,
          workspace_total = EXCLUDED.workspace_total,
          collection_interval = EXCLUDED.collection_interval,
          alert_delay_seconds = EXCLUDED.alert_delay_seconds,
          updated_at = NOW()
      `,
      [
        id,
        payload.items_per_day ?? 0,
        payload.sensors_per_day ?? 0,
        payload.bytes_per_day ?? 0,
        payload.equipments_total ?? 0,
        payload.sensors_total ?? 0,
        payload.users_total ?? 0,
        payload.organization_total ?? 0,
        payload.workspace_total ?? 0,
        payload.collection_interval ?? 60,
        payload.alert_delay_seconds ?? 1,
      ]
    );
    await auditLog(request, 'upsert', 'tenant_limits', id, payload);
    return reply.code(201).send({ status: 'ok' });
  });

  fastify.put('/tenants/:id/limits', async (request, reply) => {
    const { id } = request.params;
    const payload = request.body || {};
    await queryDatabase(
      `
        UPDATE tenant_limits
        SET
          items_per_day = COALESCE($1, items_per_day),
          sensors_per_day = COALESCE($2, sensors_per_day),
          bytes_per_day = COALESCE($3, bytes_per_day),
          equipments_total = COALESCE($4, equipments_total),
          sensors_total = COALESCE($5, sensors_total),
          users_total = COALESCE($6, users_total),
          organization_total = COALESCE($7, organization_total),
          workspace_total = COALESCE($8, workspace_total),
          collection_interval = COALESCE($9, collection_interval),
          alert_delay_seconds = COALESCE($10, alert_delay_seconds),
          updated_at = NOW()
        WHERE tenant_id = $11
      `,
      [
        payload.items_per_day,
        payload.sensors_per_day,
        payload.bytes_per_day,
        payload.equipments_total,
        payload.sensors_total,
        payload.users_total,
        payload.organization_total,
        payload.workspace_total,
        payload.collection_interval,
        payload.alert_delay_seconds,
        id,
      ]
    );
    await auditLog(request, 'update', 'tenant_limits', id, payload);
    return reply.send({ status: 'ok' });
  });

  fastify.delete('/tenants/:id/limits', async (request, reply) => {
    const { id } = request.params;
    await queryDatabase(`DELETE FROM tenant_limits WHERE tenant_id = $1`, [id]);
    await auditLog(request, 'delete', 'tenant_limits', id, {});
    return reply.send({ status: 'ok' });
  });
};
