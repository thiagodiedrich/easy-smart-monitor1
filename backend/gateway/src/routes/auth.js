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
import config from '../config.js';
import bcrypt from 'bcrypt';

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
          username: { type: 'string' },
          password: { type: 'string' },
        },
      },
    },
  }, async (request, reply) => {
    const { username, password } = request.body;
    const ipAddress = getRealIP(request);
    const tenantId = config.multiTenant.enabled
      ? request.headers[config.multiTenant.tenantHeader]
      : null;
    
    if (!username || !password) {
      return reply.code(401).send({ 
        error: 'INVALID_CREDENTIALS',
        message: 'Credenciais inválidas' 
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
    
    if (!user) {
      return reply.code(401).send({ 
        error: 'INVALID_CREDENTIALS',
        message: 'Credenciais inválidas' 
      });
    }
    
    // Verificar se retornou erro de status
    if (user.error) {
      const statusCode = user.error === 'BLOCKED' || user.error === 'LOCKED' ? 403 : 401;
      return reply.code(statusCode).send({
        error: user.error,
        message: user.message,
      });
    }
    
    // Gerar tokens
    const accessToken = fastify.jwt.sign(
      { 
        sub: user.username,
        user_id: user.id,
        tenant_id: user.tenant_id,
        organization_id: user.organization_id,
        workspace_id: user.workspace_id,
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
        organization_id: user.organization_id,
        workspace_id: user.workspace_id,
        role: user.role,
        user_type: UserType.FRONTEND,
        type: 'refresh' 
      },
      { expiresIn: '7d' }
    );

    await saveRefreshToken(user.id, refreshToken, new Date(Date.now() + 7 * 24 * 60 * 60 * 1000));
    
    logger.info('Login frontend realizado com sucesso', { 
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
          username: { type: 'string' },
          password: { type: 'string' },
          device_id: { type: 'string' }, // Opcional: ID do dispositivo
        },
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
        message: 'Credenciais inválidas' 
      });
    }
    
    // Validar credenciais (apenas tipo device)
    const user = await validateUserCredentials(
      username,
      password,
      UserType.DEVICE,
      ipAddress,
      tenantId
    );
    
    if (!user) {
      return reply.code(401).send({ 
        error: 'INVALID_CREDENTIALS',
        message: 'Credenciais inválidas' 
      });
    }
    
    // Verificar se retornou erro de status
    if (user.error) {
      const statusCode = user.error === 'BLOCKED' || user.error === 'LOCKED' ? 403 : 401;
      return reply.code(statusCode).send({
        error: user.error,
        message: user.message,
      });
    }
    
    // Gerar tokens
    const accessToken = fastify.jwt.sign(
      { 
        sub: user.username,
        user_id: user.id,
        tenant_id: user.tenant_id,
        organization_id: user.organization_id,
        workspace_id: user.workspace_id,
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
        organization_id: user.organization_id,
        workspace_id: user.workspace_id,
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
          organization_id: user.organization_id,
          workspace_id: user.workspace_id,
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
    },
  }, async (request, reply) => {
    try {
      await request.jwtVerify();
      
      return {
        username: request.user.sub,
        user_id: request.user.user_id,
        tenant_id: request.user.tenant_id,
        organization_id: request.user.organization_id,
        workspace_id: request.user.workspace_id,
        role: request.user.role,
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
