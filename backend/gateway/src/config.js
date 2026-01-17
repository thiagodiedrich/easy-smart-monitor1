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
  
  // Storage (MinIO/S3)
  storage: {
    type: process.env.STORAGE_TYPE || 'minio', // 'minio' ou 'local'
    endpoint: process.env.MINIO_ENDPOINT || 'localhost',
    port: process.env.MINIO_PORT || '9000',
    accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
    secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin',
    bucket: process.env.MINIO_BUCKET || 'telemetry-raw',
    region: process.env.MINIO_REGION || 'us-east-1',
    useSSL: process.env.MINIO_USE_SSL || 'false',
    localPath: process.env.STORAGE_LOCAL_PATH || '/app/storage',
  },
  
  // Redis
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379/0',
  
  // Rate Limiting
  rateLimitPerMinute: parseInt(process.env.RATE_LIMIT_PER_MINUTE || '1000', 10),
  
  // CORS
  corsOrigins: (process.env.CORS_ORIGINS || 'http://localhost:3000').split(','),
  
  // Logging
  logLevel: process.env.LOG_LEVEL || 'info',
  nodeEnv: process.env.NODE_ENV || 'development',
};
