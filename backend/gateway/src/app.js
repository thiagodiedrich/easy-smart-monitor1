/**
 * API Gateway - Easy Smart Monitor
 * 
 * Recebe requisições HTTP e envia para Kafka para processamento assíncrono.
 * Focado em alta performance e baixa latência.
 */
import Fastify from 'fastify';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import rateLimit from '@fastify/rate-limit';
import jwt from '@fastify/jwt';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import { kafkaProducer } from './kafka/producer.js';
import { initStorage } from './storage/storage.js';
import { initDatabasePool, closeDatabasePool } from './utils/database.js';
import { bootstrapMasterAdmin } from './utils/bootstrap.js';
import { authRoutes } from './routes/auth.js';
import { telemetryRoutes } from './routes/telemetry.js';
import { analyticsRoutes } from './routes/analytics.js';
import { healthRoutes } from './routes/health.js';
import { adminRoutes } from './routes/admin.js';
import { tenantRoutes } from './routes/tenant.js';
import { logger } from './utils/logger.js';
import { queryDatabase } from './utils/database.js';
import config from './config.js';

// Criar instância Fastify
const app = Fastify({
  logger: logger,
  requestIdLogLabel: 'reqId',
  disableRequestLogging: false,
  requestIdHeader: 'x-request-id',
  trustProxy: true, // Para rate limiting com proxy reverso
});

function getRoleName(role) {
  if (!role) return null;
  if (typeof role === 'string') return role;
  if (Array.isArray(role)) {
    if (role.includes(0) || role.includes('0')) return 'super';
    if (role.includes('admin')) return 'admin';
    if (role.includes('manager')) return 'manager';
    if (role.includes('viewer')) return 'viewer';
    return null;
  }
  if (typeof role === 'object') {
    if (role[0] === true || role['0'] === true || role.super === true) return 'super';
    if (role.role) return role.role;
    if (role.name) return role.name;
    return null;
  }
  return null;
}

// Registrar plugins
await app.register(helmet, {
  contentSecurityPolicy: false, // Ajustar conforme necessário
});

await app.register(cors, {
  origin: config.corsOrigins,
  credentials: true,
});

// Swagger/OpenAPI Documentation
await app.register(swagger, {
  openapi: {
    openapi: '3.0.0',
    info: {
      title: 'Easy Smart Monitor API',
      description: 'API RESTful escalável para recebimento e processamento de dados de telemetria',
      version: '1.3.0',
      contact: {
        name: 'Datacase',
      },
    },
    servers: [
      config.swaggerServerUrl
        ? { url: config.swaggerServerUrl, description: 'Servidor Público' }
        : { url: `http://${config.host}:${config.port}`, description: 'Servidor Local' },
    ],
    tags: [
      { name: 'Autenticação', description: 'Endpoints de autenticação e autorização' },
      { name: 'Telemetria', description: 'Envio de dados de telemetria (Claim Check Pattern)' },
      { name: 'Analytics', description: 'Consultas analíticas otimizadas (Continuous Aggregates)' },
      { name: 'Health', description: 'Health checks e status do sistema' },
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: 'http',
          scheme: 'bearer',
          bearerFormat: 'JWT',
        },
      },
    },
    security: [
      { bearerAuth: [] },
    ],
  },
});

await app.register(swaggerUi, {
  routePrefix: '/api/v1/docs',
  uiConfig: {
    docExpansion: 'list',
    deepLinking: true,
  },
  staticCSP: true,
  transformStaticCSP: (header) => header,
});

const auditLogEnabled = (process.env.AUDIT_LOG_ENABLED || 'true').toLowerCase() === 'true';

app.addHook('onRequest', async (request) => {
  request.auditStartTime = Date.now();
});

const deviceAllowedRoutes = [
  { method: 'POST', path: '/api/v1/auth/device/login' },
  { method: 'POST', path: '/api/v1/auth/refresh' },
  { method: 'GET', path: '/api/v1/auth/me' },
  { method: 'POST', path: '/api/v1/telemetry/bulk' },
  { method: 'POST', path: '/api/v1/telemetria/bulk' },
  { method: 'GET', path: '/api/v1/tenant/workspaces' },
];

app.addHook('onRequest', async (request, reply) => {
  if (!request.headers.authorization) {
    return;
  }
  try {
    await request.jwtVerify();
  } catch {
    return;
  }
  if (request.user?.user_type !== 'device') {
    return;
  }
  const path = (request.url || '').split('?')[0];
  const allowed = deviceAllowedRoutes.some(
    (route) => route.method === request.method && route.path === path
  );
  if (!allowed) {
    return reply.code(403).send({
      error: 'FORBIDDEN',
      message: 'Acesso restrito para usuário device',
    });
  }
});

app.addHook('onResponse', async (request, reply) => {
  if (!auditLogEnabled) {
    return;
  }
  try {
    const durationMs = Date.now() - (request.auditStartTime || Date.now());
    const action = `${request.method} ${request.url}`;
    const metadata = {
      method: request.method,
      url: request.url,
      statusCode: reply.statusCode,
      duration_ms: durationMs,
      ip: request.ip,
      user_agent: request.headers['user-agent'],
      request_id: request.id,
    };
    const actorRole = getRoleName(request.user?.role);
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
        actorRole,
        action,
        'api_request',
        request.id ? String(request.id) : null,
        metadata,
      ]
    );
  } catch (error) {
    logger.warn('Falha ao registrar audit log global', { error: error.message });
  }
});

// Rate limiting
const rateLimitConfig = {
  max: config.rateLimitPerMinute,
  timeWindow: '1 minute',
  nameSpace: 'easysmart-gateway',
  keyGenerator: (request) => {
    if (config.multiTenant.enabled) {
      return (
        request.headers?.[config.multiTenant.tenantHeader] ||
        request.ip
      );
    }
    return request.ip;
  },
};

// Redis para rate limiting e shield
if (config.redisUrl) {
  try {
    // Parse Redis URL
    const redisUrl = config.redisUrl.replace('redis://', '');
    const [hostPort, db] = redisUrl.split('/');
    const [host, port] = hostPort.split(':');
    
    // Registrar @fastify/redis
    await app.register(import('@fastify/redis'), {
      host: host || 'redis',
      port: parseInt(port || '6379', 10),
      db: parseInt(db || '0', 10),
    });
    
    rateLimitConfig.redis = app.redis;
    logger.info('Redis configurado para rate limiting e shield', {
      host: host || 'redis',
      port: port || '6379',
    });
  } catch (error) {
    logger.warn('Redis não disponível, usando rate limiting em memória', { error: error.message });
  }
}

await app.register(rateLimit, rateLimitConfig);

// Registrar Shield Plugin (Defense in Depth) - DEPOIS do Redis
if (app.redis) {
  try {
    await app.register(import('./plugins/shield.js'));
    logger.info('Shield plugin registrado');
  } catch (error) {
    logger.warn('Erro ao registrar Shield plugin', { error: error.message });
  }
}

// JWT
await app.register(jwt, {
  secret: config.jwtSecret,
  sign: {
    algorithm: 'HS256',
    expiresIn: config.jwtExpiresIn,
  },
});

// Contexto multi-tenant (Fase 0 - opcional)
if (config.multiTenant.enabled) {
  try {
    await app.register(import('./plugins/tenant-context.js'));
    logger.info('Tenant context plugin registrado', {
      enforce: config.multiTenant.enforce,
    });
  } catch (error) {
    logger.warn('Erro ao registrar tenant context plugin', { error: error.message });
  }
}

// Inicializar Storage (MinIO)
initStorage();

// Inicializar pool de conexões do banco
initDatabasePool();

// Bootstrap usuário master (se habilitado)
await bootstrapMasterAdmin();

// Registrar rotas
await app.register(authRoutes, { prefix: '/api/v1/auth' });
await app.register(telemetryRoutes, { prefix: '/api/v1/telemetry' });
await app.register(telemetryRoutes, { prefix: '/api/v1/telemetria' }); // Compatibilidade
await app.register(analyticsRoutes, { prefix: '/api/v1' });
await app.register(healthRoutes, { prefix: '/api/v1/health' });
await app.register(adminRoutes, { prefix: '/api/v1/admin' });
await app.register(tenantRoutes, { prefix: '/api/v1/tenant' });

// Rota raiz
app.get('/', async (request, reply) => {
  return {
    name: 'Easy Smart Monitor Gateway',
      version: '1.3.0',
    status: 'online',
    docs: '/api/v1/docs',
  };
});

// Hook de shutdown
app.addHook('onClose', async () => {
  logger.info('Fechando conexões...');
  await kafkaProducer.disconnect();
  await closeDatabasePool();
  logger.info('Conexões fechadas');
});

// Handler de erros global
app.setErrorHandler((error, request, reply) => {
  logger.error('Erro não tratado', {
    error: error.message,
    stack: error.stack,
    url: request.url,
    method: request.method,
  });
  
  reply.status(error.statusCode || 500).send({
    error: error.message || 'Erro interno do servidor',
    statusCode: error.statusCode || 500,
  });
});

// Iniciar servidor
const start = async () => {
  try {
    await app.listen({
      port: config.port,
      host: config.host,
    });
    
    logger.info(`🚀 Gateway rodando em http://${config.host}:${config.port}`);
  } catch (err) {
    logger.error(err);
    process.exit(1);
  }
};

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM recebido, encerrando graciosamente...');
  await app.close();
  process.exit(0);
});

process.on('SIGINT', async () => {
  logger.info('SIGINT recebido, encerrando graciosamente...');
  await app.close();
  process.exit(0);
});

start();

export default app;
