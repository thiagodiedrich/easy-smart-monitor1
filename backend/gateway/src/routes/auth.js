/**
 * Rotas de Autenticação
 * 
 * Gerencia login e refresh tokens para dois tipos de usuários:
 * - Frontend: Dashboard e outras integrações web
 * - Device: Dispositivos IoT (Home Assistant, etc.)
 * 
 * Cada tipo de usuário só pode fazer login na sua API específica.
 */
import { logger } from '../utils/logger.js';
import { validateUserCredentials, UserType } from '../utils/auth.js';
import { queryDatabase } from '../utils/database.js';
import { getEffectivePermissions } from '../utils/permissions.js';
import config from '../config.js';
import bcrypt from 'bcrypt';

const maxAttempts = parseInt(process.env.LOGIN_MAX_ATTEMPTS || '5', 10);
const blockMinutes = parseInt(process.env.LOGIN_BLOCK_MINUTES || '30', 10);

const errorResponseSchema = {
  type: 'object',
  properties: {
    error: {
      type: 'string',
      enum: [
        'INVALID_CREDENTIALS',
        'BLOCKED',
        'INACTIVE',
        'LOCKED',
        'INVALID_TOKEN',
        'INVALID_TOKEN_TYPE',
        'MISSING_TOKEN',
        'INVALID_USER_TYPE',
        'INVALID_SCOPE',
        'UNAUTHORIZED',
      ],
    },
    message: { type: 'string' },
  },
};

function normalizeScopeArrayValue(value) {
  if (value === undefined || value === null) {
    return value;
  }
  if (Array.isArray(value)) {
    const flat = value.flat(Infinity)
      .map((item) => parseInt(item, 10))
      .filter((item) => !Number.isNaN(item));
    if (flat.length === 0) {
      return [];
    }
    if (flat.includes(0)) {
      return [0];
    }
    return flat;
  }
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? value : parsed;
}

function isValidDeviceScope(user) {
  if (!user) return false;
  if (Number(user.tenant_id) === 0) return false;
  if (!Array.isArray(user.organization_id) || user.organization_id.length !== 1) return false;
  if (user.organization_id.includes(0)) return false;
  if (!Array.isArray(user.workspace_id) || user.workspace_id.length !== 1) return false;
  if (user.workspace_id.includes(0)) return false;
  return true;
}

/**
 * Obtém IP real do cliente
 */
function getRealIP(request) {
  return request.headers['x-forwarded-for']?.split(',')[0]?.trim() ||
         request.headers['x-real-ip'] ||
         request.ip ||
         request.socket.remoteAddress;
}

async function saveRefreshToken(userId, refreshToken, expiresAt) {
  const hash = await bcrypt.hash(refreshToken, 10);
  await queryDatabase(
    `
      UPDATE users
      SET refresh_token_hash = $1,
          refresh_token_expires_at = $2
      WHERE id = $3
    `,
    [hash, expiresAt, userId]
  );
}

export const authRoutes = async (fastify) => {
  /**
   * POST /api/v1/auth/login
   * 
   * Autenticação para Frontend/Dashboard.
   * Apenas usuários do tipo 'frontend' podem usar este endpoint.
   */
  fastify.post('/login', {
    schema: {
      description: 'Autentica usuário frontend/dashboard',
      tags: ['Autenticação'],
      body: {
        type: 'object',
        required: ['username', 'password'],
        properties: {
          username: { type: 'string', description: 'Ex: admin@admin.com' },
          password: { type: 'string', description: 'Ex: admin1234..' },
        },
      },
      response: {
        200: {
          type: 'object',
          properties: {
            access_token: { type: 'string', description: 'JWT de acesso' },
            refresh_token: { type: 'string', description: 'JWT de refresh' },
            token_type: { type: 'string', description: 'bearer' },
            expires_in: { type: 'number', description: 'Segundos até expirar' },
          },
        },
        401: errorResponseSchema,
        403: errorResponseSchema,
      },
    },
  }, async (request, reply) => {
    const { username, password } = request.body;
    const ipAddress = getRealIP(request);
    const tenantId = config.multiTenant.enabled
      ? request.headers[config.multiTenant.tenantHeader]
      : null;
    
    if (!username || !password) {
      logger.info('Login frontend branch: missing credentials', { username });
      return reply.code(401).send({ 
        error: 'INVALID_CREDENTIALS',
        message: `Credenciais inválidas. Após ${maxAttempts} tentativas seguidas, você ficará bloqueado por ${blockMinutes} minutos.` 
      });
    }
    
    // Validar credenciais (apenas tipo frontend)
    const user = await validateUserCredentials(
      username,
      password,
      UserType.FRONTEND,
      ipAddress,
      tenantId
    );

    const debugPayload = {
      username,
      userFound: Boolean(user),
      error: user?.error || null,
      status: user?.status || null,
      userType: user?.user_type || null,
    };
    logger.info(`Login frontend debug: ${JSON.stringify(debugPayload)}`);
    
    if (!user) {
      logger.info('Login frontend branch: user not found', { username });
      return reply.code(401).send({ 
        error: 'INVALID_CREDENTIALS',
        message: `Credenciais inválidas. Após ${maxAttempts} tentativas seguidas, você ficará bloqueado por ${blockMinutes} minutos.` 
      });
    }
    
    // Verificar se retornou erro de status
    if (user.error) {
      logger.info('Login frontend branch: user error', { username, reason: user.error });
      const statusCode = user.error === 'BLOCKED' || user.error === 'LOCKED' ? 403 : 401;
      return reply.code(statusCode).send({
        error: user.error,
        message: user.message,
      });
    }
    
    // Gerar tokens
    const normalizedOrganizationId = normalizeScopeArrayValue(user.organization_id);
    const normalizedWorkspaceId = normalizeScopeArrayValue(user.workspace_id);
    const accessToken = fastify.jwt.sign(
      { 
        sub: user.username,
        user_id: user.id,
        tenant_id: user.tenant_id,
        organization_id: normalizedOrganizationId,
        workspace_id: normalizedWorkspaceId,
        role: user.role,
        user_type: UserType.FRONTEND,
        type: 'access' 
      },
      { expiresIn: config.jwtExpiresIn }
    );
    
    const refreshToken = fastify.jwt.sign(
      { 
        sub: user.username,
        user_id: user.id,
        tenant_id: user.tenant_id,
        organization_id: normalizedOrganizationId,
        workspace_id: normalizedWorkspaceId,
        role: user.role,
        user_type: UserType.FRONTEND,
        type: 'refresh' 
      },
      { expiresIn: '7d' }
    );

    await saveRefreshToken(user.id, refreshToken, new Date(Date.now() + 7 * 24 * 60 * 60 * 1000));
    
    logger.info('Login frontend branch: success', { 
      username,
      user_id: user.id,
      ip: ipAddress,
    });
    
    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'bearer',
      expires_in: parseInt(config.jwtExpiresIn) * 60 || 900,
    };
  });
  
  /**
   * POST /api/v1/auth/device/login
   * 
   * Autenticação para Dispositivos IoT.
   * Apenas usuários do tipo 'device' podem usar este endpoint.
   */
  fastify.post('/device/login', {
    schema: {
      description: 'Autentica dispositivo IoT',
      tags: ['Autenticação'],
      body: {
        type: 'object',
        required: ['username', 'password'],
        properties: {
          username: { type: 'string', description: 'Ex: device-01' },
          password: { type: 'string', description: 'Ex: device123' },
          device_id: { type: 'string', description: 'Ex: iot-abc-001' }, // Opcional: ID do dispositivo
        },
      },
      response: {
        200: {
          type: 'object',
          properties: {
            access_token: { type: 'string', description: 'JWT de acesso' },
            refresh_token: { type: 'string', description: 'JWT de refresh' },
            token_type: { type: 'string', description: 'bearer' },
            expires_in: { type: 'number', description: 'Segundos até expirar' },
          },
        },
        401: errorResponseSchema,
        403: errorResponseSchema,
      },
    },
  }, async (request, reply) => {
    const { username, password, device_id } = request.body;
    const ipAddress = getRealIP(request);
    const tenantId = config.multiTenant.enabled
      ? request.headers[config.multiTenant.tenantHeader]
      : null;
    
    if (!username || !password) {
      return reply.code(401).send({ 
        error: 'INVALID_CREDENTIALS',
        message: `Credenciais inválidas. Após ${maxAttempts} tentativas seguidas, você ficará bloqueado por ${blockMinutes} minutos.` 
      });
    }
    
    // Buscar usuário por username (sem filtrar tipo)
    const query = `
      SELECT 
        id,
        username,
        email,
        hashed_password,
        tenant_id,
        organization_id,
        workspace_id,
        role,
        user_type,
        status,
        failed_login_attempts,
        locked_until
      FROM users
      WHERE username = $1
      ${tenantId ? 'AND tenant_id = $2' : ''}
    `;
    const params = tenantId ? [username, tenantId] : [username];
    const result = await queryDatabase(query, params);
    const user = result?.[0];
    
    if (!user) {
      return reply.code(401).send({ 
        error: 'INVALID_CREDENTIALS',
        message: `Credenciais inválidas. Após ${maxAttempts} tentativas seguidas, você ficará bloqueado por ${blockMinutes} minutos.` 
      });
    }

    if (user.user_type !== UserType.DEVICE) {
      return reply.code(403).send({
        error: 'INVALID_USER_TYPE',
        message: 'Usuário deve ser do tipo device para este login',
      });
    }
    
    // Verificar se retornou erro de status
    if (user.status === 'blocked') {
      return reply.code(403).send({
        error: 'BLOCKED',
        message: 'Usuário bloqueado. Contate o administrador.',
      });
    }
    if (user.status === 'inactive') {
      return reply.code(401).send({
        error: 'INACTIVE',
        message: 'Usuário inativo. Contate o administrador.',
      });
    }
    if (user.locked_until) {
      const lockedUntil = new Date(user.locked_until);
      if (lockedUntil > new Date()) {
        return reply.code(403).send({
          error: 'LOCKED',
          message: `Usuário bloqueado temporariamente até ${lockedUntil.toISOString()}`,
        });
      }
    }

    const passwordValid = await bcrypt.compare(password, user.hashed_password);
    if (!passwordValid) {
      await queryDatabase(
        `
          UPDATE users
          SET 
            failed_login_attempts = failed_login_attempts + 1,
            locked_until = CASE
              WHEN failed_login_attempts + 1 >= $2 THEN NOW() + ($3::text || ' minutes')::interval
              ELSE locked_until
            END
          WHERE id = $1
        `,
        [user.id, maxAttempts, blockMinutes]
      );
      return reply.code(401).send({
        error: 'INVALID_CREDENTIALS',
        message: `Credenciais inválidas. Após ${maxAttempts} tentativas seguidas, você ficará bloqueado por ${blockMinutes} minutos.`,
      });
    }

    await queryDatabase(
      `
        UPDATE users
        SET 
          last_login_at = NOW(),
          last_login_ip = $1,
          failed_login_attempts = 0,
          locked_until = NULL
        WHERE id = $2
      `,
      [ipAddress, user.id]
    );

    if (!isValidDeviceScope(user)) {
      return reply.code(403).send({
        error: 'INVALID_SCOPE',
        message: 'Usuário device deve ter tenant_id, 1 organization_id e 1 workspace_id válidos',
      });
    }
    
    // Gerar tokens
    const normalizedOrganizationId = normalizeScopeArrayValue(user.organization_id);
    const normalizedWorkspaceId = normalizeScopeArrayValue(user.workspace_id);
    const accessToken = fastify.jwt.sign(
      { 
        sub: user.username,
        user_id: user.id,
        tenant_id: user.tenant_id,
        organization_id: normalizedOrganizationId,
        workspace_id: normalizedWorkspaceId,
        role: user.role,
        user_type: UserType.DEVICE,
        device_id: device_id || 'unknown',
        type: 'access' 
      },
      { expiresIn: config.jwtExpiresIn }
    );
    
    const refreshToken = fastify.jwt.sign(
      { 
        sub: user.username,
        user_id: user.id,
        tenant_id: user.tenant_id,
        organization_id: normalizedOrganizationId,
        workspace_id: normalizedWorkspaceId,
        role: user.role,
        user_type: UserType.DEVICE,
        device_id: device_id || 'unknown',
        type: 'refresh' 
      },
      { expiresIn: '30d' } // Refresh token mais longo para dispositivos
    );

    await saveRefreshToken(user.id, refreshToken, new Date(Date.now() + 30 * 24 * 60 * 60 * 1000));
    
    logger.info('Login device realizado com sucesso', { 
      username,
      user_id: user.id,
      device_id: device_id || 'unknown',
      ip: ipAddress,
    });
    
    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'bearer',
      expires_in: parseInt(config.jwtExpiresIn) * 60 || 900,
    };
  });
  
  /**
   * POST /api/v1/auth/refresh
   * 
   * Renova access token usando refresh token.
   * Funciona para ambos os tipos de usuário.
   */
  fastify.post('/refresh', {
    schema: {
      description: 'Renova access token',
      tags: ['Autenticação'],
      response: {
        200: {
          type: 'object',
          properties: {
            access_token: { type: 'string', description: 'JWT de acesso' },
            token_type: { type: 'string', description: 'bearer' },
            expires_in: { type: 'number', description: 'Segundos até expirar' },
          },
        },
        401: errorResponseSchema,
      },
    },
  }, async (request, reply) => {
    try {
      const authHeader = request.headers.authorization;
      
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return reply.code(401).send({ 
          error: 'MISSING_TOKEN',
          message: 'Header Authorization ausente' 
        });
      }
      
      const token = authHeader.replace('Bearer ', '').trim();
      
      if (!token) {
        return reply.code(401).send({ 
          error: 'INVALID_TOKEN',
          message: 'Token não fornecido' 
        });
      }
      
      const decoded = fastify.jwt.verify(token);
      
      if (decoded.type !== 'refresh') {
        return reply.code(401).send({ 
          error: 'INVALID_TOKEN_TYPE',
          message: 'Token não é do tipo refresh' 
        });
      }

      const userRows = await queryDatabase(
        `
          SELECT id, tenant_id, organization_id, workspace_id, role, refresh_token_hash, refresh_token_expires_at
          FROM users
          WHERE id = $1
        `,
        [decoded.user_id]
      );
      if (!userRows || userRows.length === 0) {
        return reply.code(401).send({
          error: 'INVALID_TOKEN',
          message: 'Usuário não encontrado'
        });
      }
      const user = userRows[0];
      if (user.refresh_token_hash) {
        if (user.refresh_token_expires_at && new Date(user.refresh_token_expires_at) < new Date()) {
          return reply.code(401).send({
            error: 'INVALID_TOKEN',
            message: 'Refresh token expirado'
          });
        }
        const validRefresh = await bcrypt.compare(token, user.refresh_token_hash);
        if (!validRefresh) {
          return reply.code(401).send({
            error: 'INVALID_TOKEN',
            message: 'Refresh token inválido'
          });
        }
      } else {
        logger.warn('Refresh token sem hash registrado (migração pendente)', {
          user_id: decoded.user_id
        });
      }
      
      // Gerar novo access token (preservar user_type)
      const accessToken = fastify.jwt.sign(
        { 
          sub: decoded.sub,
          user_id: decoded.user_id,
          tenant_id: user.tenant_id,
          organization_id: normalizeScopeArrayValue(user.organization_id),
          workspace_id: normalizeScopeArrayValue(user.workspace_id),
          role: user.role,
          user_type: decoded.user_type,
          device_id: decoded.device_id,
          type: 'access' 
        },
        { expiresIn: config.jwtExpiresIn }
      );
      
      logger.info('Token renovado', { 
        username: decoded.sub,
        user_type: decoded.user_type,
      });
      
      return {
        access_token: accessToken,
        token_type: 'bearer',
        expires_in: parseInt(config.jwtExpiresIn) * 60 || 900,
      };
    } catch (error) {
      logger.warn('Erro ao renovar token', { error: error.message });
      return reply.code(401).send({ 
        error: 'INVALID_TOKEN',
        message: 'Token inválido ou expirado' 
      });
    }
  });
  
  /**
   * GET /api/v1/auth/me
   * 
   * Retorna informações do usuário autenticado.
   */
  fastify.get('/me', {
    schema: {
      description: 'Informações do usuário autenticado',
      tags: ['Autenticação'],
      response: {
        200: {
          type: 'object',
          properties: {
            username: { type: 'string', description: 'Ex: admin@admin.com' },
            user_id: { type: 'number', description: 'Ex: 1' },
            tenant_id: { type: 'number', description: 'Ex: 0' },
            organization_id: {
              oneOf: [
                { type: 'number', description: 'Ex: 1' },
                { type: 'array', items: { type: 'number' }, description: 'Ex: [1,2]' },
              ],
            },
            workspace_id: {
              oneOf: [
                { type: 'number', description: 'Ex: 10' },
                { type: 'array', items: { type: 'number' }, description: 'Ex: [10,11]' },
              ],
            },
            role: {
              oneOf: [
                { type: 'object', description: 'Ex: {"role":"admin"}' },
                { type: 'array', items: { type: 'number' }, description: 'Ex: [0]' },
              ],
            },
            permissions: {
              type: 'array',
              items: { type: 'string' },
              description: 'Permissões efetivas do usuário',
            },
            user_type: { type: 'string', description: 'frontend | device' },
            device_id: { type: 'string', description: 'Ex: iot-abc-001' },
          },
        },
        401: errorResponseSchema,
        403: errorResponseSchema,
      },
    },
  }, async (request, reply) => {
    try {
      await request.jwtVerify();

      if (request.user.user_type === UserType.DEVICE && !isValidDeviceScope(request.user)) {
        return reply.code(403).send({
          error: 'INVALID_SCOPE',
          message: 'Usuário device deve ter 1 organization_id e 1 workspace_id válidos',
        });
      }
      
      let effectivePermissions = [];
      try {
        effectivePermissions = getEffectivePermissions(request.user.role);
      } catch (err) {
        logger.error('Erro ao obter permissões do usuário', { error: err.message, role: request.user.role });
      }
      
      return {
        username: request.user.sub,
        user_id: request.user.user_id,
        tenant_id: request.user.tenant_id,
        organization_id: normalizeScopeArrayValue(request.user.organization_id),
        workspace_id: normalizeScopeArrayValue(request.user.workspace_id),
        role: request.user.role,
        permissions: effectivePermissions,
        user_type: request.user.user_type,
        device_id: request.user.device_id,
      };
    } catch (error) {
      logger.warn('Auth /me não autorizado', {
        error: error.message,
        hasAuthorizationHeader: Boolean(request.headers.authorization),
        forwardedProto: request.headers['x-forwarded-proto'],
        forwardedFor: request.headers['x-forwarded-for'],
      });
      return reply.code(401).send({ 
        error: 'UNAUTHORIZED',
        message: 'Não autorizado' 
      });
    }
  });
};

export default authRoutes;
