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
import { kafkaProducer } from './kafka/producer.js';
import { initStorage } from './storage/storage.js';
import { initDatabasePool, closeDatabasePool } from './utils/database.js';
import { authRoutes } from './routes/auth.js';
import { telemetryRoutes } from './routes/telemetry.js';
import { analyticsRoutes } from './routes/analytics.js';
import { healthRoutes } from './routes/health.js';
import { logger } from './utils/logger.js';
import config from './config.js';

// Criar instância Fastify
const app = Fastify({
  logger: logger,
  requestIdLogLabel: 'reqId',
  disableRequestLogging: false,
  requestIdHeader: 'x-request-id',
  trustProxy: true, // Para rate limiting com proxy reverso
});

// Registrar plugins
await app.register(helmet, {
  contentSecurityPolicy: false, // Ajustar conforme necessário
});

await app.register(cors, {
  origin: config.corsOrigins,
  credentials: true,
});

// Rate limiting
const rateLimitConfig = {
  max: config.rateLimitPerMinute,
  timeWindow: '1 minute',
  nameSpace: 'easysmart-gateway',
};

// Adicionar Redis se disponível
if (config.redisUrl) {
  try {
    const Redis = (await import('ioredis')).default;
    rateLimitConfig.redis = new Redis(config.redisUrl);
    logger.info('Rate limiting com Redis configurado');
  } catch (error) {
    logger.warn('Redis não disponível, usando rate limiting em memória', { error: error.message });
  }
}

await app.register(rateLimit, rateLimitConfig);

// JWT
await app.register(jwt, {
  secret: config.jwtSecret,
  sign: {
    algorithm: 'HS256',
    expiresIn: config.jwtExpiresIn,
  },
});

// Inicializar Storage (MinIO)
initStorage();

// Inicializar pool de conexões do banco
initDatabasePool();

// Registrar rotas
await app.register(authRoutes, { prefix: '/api/v1/auth' });
await app.register(telemetryRoutes, { prefix: '/api/v1/telemetry' });
await app.register(telemetryRoutes, { prefix: '/api/v1/telemetria' }); // Compatibilidade
await app.register(analyticsRoutes, { prefix: '/api/v1' });
await app.register(healthRoutes, { prefix: '/api/v1/health' });

// Rota raiz
app.get('/', async (request, reply) => {
  return {
    name: 'Easy Smart Monitor Gateway',
    version: '1.0.0',
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
