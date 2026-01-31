/**
 * Configurações do Gateway
 */
import dotenv from 'dotenv';

dotenv.config();

export default {
  // Servidor
  host: process.env.HOST || '0.0.0.0',
  port: parseInt(process.env.PORT || '8000', 10),
  
  // JWT
  jwtSecret: process.env.SECRET_KEY || 'change-me-in-production',
  jwtExpiresIn: process.env.ACCESS_TOKEN_EXPIRE_MINUTES 
    ? `${process.env.ACCESS_TOKEN_EXPIRE_MINUTES}m`
    : '15m',
  
  // Kafka
  kafka: {
    brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
    clientId: 'easysmart-gateway',
    topic: process.env.KAFKA_TOPIC || 'telemetry.raw',
  },
  
  // Storage (MinIO/S3) - endPoint deve ser só host; porta fica em port (exigência do cliente MinIO)
  storage: (() => {
    const raw = process.env.MINIO_ENDPOINT || 'localhost';
    const hasPort = raw.includes(':');
    const endpoint = hasPort ? raw.slice(0, raw.indexOf(':')) : raw;
    const port = process.env.MINIO_PORT || (hasPort ? raw.slice(raw.indexOf(':') + 1) : '9000');
    return {
      type: process.env.STORAGE_TYPE || 'minio',
      endpoint,
      port: String(port),
      accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
      secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin',
      bucket: process.env.MINIO_BUCKET || 'telemetry-raw',
      region: process.env.MINIO_REGION || 'us-east-1',
      useSSL: process.env.MINIO_USE_SSL || 'false',
      localPath: process.env.STORAGE_LOCAL_PATH || '/app/storage',
    };
  })(),
  
  // Redis
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379/0',
  
  // Rate Limiting
  rateLimitPerMinute: parseInt(process.env.RATE_LIMIT_PER_MINUTE || '1000', 10),
  
  // CORS
  corsOrigins: (process.env.CORS_ORIGINS || 'http://localhost:3000').split(','),

  // Swagger/OpenAPI (opcional - útil atrás de proxy HTTPS)
  swaggerServerUrl: process.env.SWAGGER_SERVER_URL || process.env.PUBLIC_URL || '',
  
  // Logging
  logLevel: process.env.LOG_LEVEL || 'info',
  nodeEnv: process.env.NODE_ENV || 'development',

  // Multi-tenant (Fase 0 - desativado por padrão)
  multiTenant: {
    enabled: (process.env.MULTI_TENANT_ENABLED || 'false').toLowerCase() === 'true',
    enforce: (process.env.MULTI_TENANT_ENFORCE || 'false').toLowerCase() === 'true',
    tenantHeader: process.env.TENANT_HEADER || 'x-tenant-id',
    organizationHeader: process.env.ORGANIZATION_HEADER || 'x-organization-id',
    workspaceHeader: process.env.WORKSPACE_HEADER || 'x-workspace-id',
  },

  // Quotas / Billing (Fase 5)
  quota: {
    enabled: (process.env.QUOTA_ENABLED || 'false').toLowerCase() === 'true',
    enforce: (process.env.QUOTA_ENFORCE || 'false').toLowerCase() === 'true',
    estimateBytes: (process.env.QUOTA_ESTIMATE_BYTES || 'false').toLowerCase() === 'true',
  },

  // Billing / Eventos (Fase 6)
  billing: {
    eventsEnabled: (process.env.BILLING_EVENTS_ENABLED || 'false').toLowerCase() === 'true',
  },
};
