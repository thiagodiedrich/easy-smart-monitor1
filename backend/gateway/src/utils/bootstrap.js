/**
 * Bootstrap de usuário master (admin global).
 *
 * Cria um usuário admin via .env para uso inicial no dashboard.
 */
import bcrypt from 'bcrypt';
import { queryDatabase } from './database.js';
import { logger } from './logger.js';

function parseIntOrNull(value, fallback = null) {
  if (value === undefined || value === null || value === '') {
    return fallback;
  }
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

export async function bootstrapMasterAdmin() {
  const enabled = (process.env.MASTER_ADMIN_ENABLED || 'false').toLowerCase() === 'true';
  if (!enabled) {
    return;
  }

  const name = process.env.MASTER_ADMIN_NAME || null;
  const username = process.env.MASTER_ADMIN_USERNAME;
  const password = process.env.MASTER_ADMIN_PASSWORD;
  const email = process.env.MASTER_ADMIN_EMAIL || null;
  const tenantId = parseIntOrNull(process.env.MASTER_ADMIN_TENANT_ID, 0);
  const organizationId = parseIntOrNull(process.env.MASTER_ADMIN_ORGANIZATION_ID, 0);
  const workspaceId = parseIntOrNull(process.env.MASTER_ADMIN_WORKSPACE_ID, 0);
  const defaultPlanCode = process.env.DEFAULT_PLAN_CODE || null;
  const roleEnv = process.env.MASTER_ADMIN_ROLE || '{0}';

  let roleValue = [0];
  try {
    if (roleEnv) {
      const normalized = roleEnv === '{0}' ? '[0]' : roleEnv;
      roleValue = JSON.parse(normalized);
    }
  } catch {
    roleValue = [0];
  }

  if (!username || !password) {
    logger.warn('MASTER_ADMIN habilitado, mas username/senha não definidos');
    return;
  }

  // Garantir tenant do sistema (id=0) para admin global
  if (tenantId === 0) {
    const tenantExists = await queryDatabase(
      'SELECT id FROM tenants WHERE id = $1',
      [tenantId]
    );
    if (!tenantExists || tenantExists.length === 0) {
      await queryDatabase(
        `
          INSERT INTO tenants (id, name, slug, status, plan_code, is_white_label, created_at, updated_at)
          VALUES ($1, $2, $3, $4, $5, FALSE, NOW(), NOW())
        `,
        [0, 'System', 'system', 'active', defaultPlanCode]
      );
      logger.info('Tenant sistema criado (id=0)');
    }

    const orgExists = await queryDatabase(
      'SELECT id FROM organizations WHERE id = $1',
      [organizationId]
    );
    if (!orgExists || orgExists.length === 0) {
      await queryDatabase(
        `
          INSERT INTO organizations (id, tenant_id, name, created_at, updated_at)
          VALUES ($1, $2, $3, NOW(), NOW())
          ON CONFLICT DO NOTHING
        `,
        [organizationId, tenantId, 'System Org']
      );
    }

    const wsExists = await queryDatabase(
      'SELECT id FROM workspaces WHERE id = $1',
      [workspaceId]
    );
    if (!wsExists || wsExists.length === 0) {
      await queryDatabase(
        `
          INSERT INTO workspaces (id, organization_id, name, created_at, updated_at)
          VALUES ($1, $2, $3, NOW(), NOW())
          ON CONFLICT DO NOTHING
        `,
        [workspaceId, organizationId, 'System Workspace']
      );
    }
  }

  // Verificar se já existe super admin global (role [0] ou flag is_superadmin)
  const existingSuper = await queryDatabase(
    `SELECT id FROM users WHERE is_superadmin = TRUE OR role @> '[0]'::jsonb LIMIT 1`
  );
  if (existingSuper && existingSuper.length > 0) {
    logger.info('Super admin já existe, bootstrap ignorado');
    return;
  }

  // Verificar se usuário já existe por username
  const existingByUsername = await queryDatabase(
    'SELECT id FROM users WHERE username = $1',
    [username]
  );
  if (existingByUsername && existingByUsername.length > 0) {
    logger.info('Usuário master já existe, bootstrap ignorado', { username });
    return;
  }

  const hashedPassword = await bcrypt.hash(password, 10);

  await queryDatabase(
    `
      INSERT INTO users (
        name,
        username,
        email,
        hashed_password,
        user_type,
        status,
        failed_login_attempts,
        locked_until,
        tenant_id,
        organization_id,
        workspace_id,
        role,
        is_superadmin,
        created_at,
        updated_at
      ) VALUES ($1, $2, $3, $4, 'frontend', 'active', 0, NULL, $5, $6, $7, $8::jsonb, TRUE, NOW(), NOW())
    `,
    [name || username, username, email, hashedPassword, tenantId, [organizationId], [workspaceId], JSON.stringify(roleValue)]
  );

  logger.info('Usuário master criado com sucesso', {
    username,
    tenant_id: tenantId,
    organization_id: organizationId,
    workspace_id: workspaceId,
  });
}
