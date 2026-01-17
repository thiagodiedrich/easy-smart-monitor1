/**
 * Rotas de Health Check
 */
import { kafkaProducer } from '../kafka/producer.js';
import { logger } from '../utils/logger.js';

export const healthRoutes = async (fastify) => {
  /**
   * GET /api/v1/health
   * 
   * Health check básico.
   */
  fastify.get('/', async (request, reply) => {
    return {
      status: 'healthy',
      service: 'gateway',
      timestamp: new Date().toISOString(),
    };
  });
  
  /**
   * GET /api/v1/health/detailed
   * 
   * Health check detalhado com verificação de dependências.
   */
  fastify.get('/detailed', async (request, reply) => {
    const checks = {
      gateway: { status: 'healthy', message: 'Gateway operacional' },
      kafka: { status: 'unknown', message: 'Verificando...' },
    };
    
    // Verificar Kafka
    try {
      // Verificar se producer está conectado
      const admin = kafkaProducer.admin();
      await admin.connect();
      
      const topics = await admin.listTopics();
      const metadata = await admin.describeCluster();
      
      await admin.disconnect();
      
      checks.kafka = {
        status: 'healthy',
        message: 'Kafka conectado',
        topics: topics.length,
        brokers: metadata.brokers.length,
      };
    } catch (error) {
      logger.error('Erro ao verificar Kafka', { error: error.message });
      checks.kafka = {
        status: 'unhealthy',
        message: error.message,
      };
    }
    
    const allHealthy = Object.values(checks).every(
      (check) => check.status === 'healthy'
    );
    
    return {
      status: allHealthy ? 'healthy' : 'degraded',
      checks,
      timestamp: new Date().toISOString(),
    };
  });
};
