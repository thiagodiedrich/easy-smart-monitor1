/**
 * Rotas de Telemetria
 * 
 * Recebe dados de telemetria, salva em Object Storage e envia Claim Check para Kafka.
 * Implementa Claim Check Pattern para payloads grandes.
 */
import { sendTelemetryToKafka } from '../kafka/producer.js';
import { saveTelemetryToStorage } from '../storage/storage.js';
import { logger } from '../utils/logger.js';
import config from '../config.js';

export const telemetryRoutes = async (fastify) => {
  // Middleware de autenticação
  fastify.addHook('onRequest', async (request, reply) => {
    try {
      await request.jwtVerify();
    } catch (err) {
      reply.code(401).send({ error: 'Não autorizado' });
    }
  });
  
  /**
   * POST /api/v1/telemetry/bulk
   * 
   * Recebe lote de telemetria e envia para Kafka.
   * Responde imediatamente sem aguardar processamento.
   */
  fastify.post('/bulk', {
    schema: {
      description: 'Recebe lote de dados de telemetria',
      tags: ['Telemetria'],
      body: {
        type: 'array',
        items: {
          type: 'object',
          required: ['equip_uuid'],
          properties: {
            equip_uuid: { type: 'string' },
            equip_nome: { type: 'string' },
            equip_local: { type: 'string' },
            equip_status: { type: 'string' },
            equip_intervalo_coleta: { type: 'number' },
            equip_sirene_ativa: { type: 'string' },
            equip_sirete_tempo: { type: 'number' },
            sensor: {
              type: 'array',
              items: { 
                type: 'object',
                properties: {
                  sensor_uuid: { type: 'string' },
                  sensor_nome: { type: 'string' },
                  sensor_tipo: { type: 'string' },
                  sensor_telemetria: { type: ['string', 'number'] },
                  sensor_datahora_coleta: { type: 'string' },
                  valor: { type: ['number', 'null'] },
                  status: { type: ['string', 'null'] },
                  timestamp: { type: 'string' },
                }
              },
            },
          },
        },
        maxItems: parseInt(process.env.MAX_BULK_SIZE || '10000', 10),
      },
      response: {
        202: {
          type: 'object',
          properties: {
            status: { type: 'string' },
            received: { type: 'number' },
            message: { type: 'string' },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { body: data } = request;
    const userId = request.user.sub; // Do JWT
    const requestId = request.id;
    
    // Validação básica
    if (!Array.isArray(data) || data.length === 0) {
      return reply.code(400).send({
        error: 'Dados inválidos. Esperado array não vazio.',
      });
    }
    
    // Verificar tamanho máximo
    const maxSize = parseInt(process.env.MAX_BULK_SIZE || '10000', 10);
    if (data.length > maxSize) {
      return reply.code(400).send({
        error: `Lote muito grande. Máximo: ${maxSize} itens`,
      });
    }
    
    // Validar estrutura básica
    for (const item of data) {
      if (!item.equip_uuid) {
        return reply.code(400).send({
          error: 'Item sem equip_uuid',
        });
      }
      if (!item.sensor || !Array.isArray(item.sensor) || item.sensor.length === 0) {
        return reply.code(400).send({
          error: 'Item sem lista de sensores válida',
        });
      }
    }
    
    try {
      // CLAIM CHECK PATTERN: Salvar arquivo em Object Storage
      const claimCheck = await saveTelemetryToStorage(data, {
        userId,
        username: request.user.sub,
        requestId,
        itemsCount: data.length,
      });
      
      // Enviar apenas Claim Check (referência) para Kafka (não bloqueia)
      await sendTelemetryToKafka(claimCheck, {
        userId,
        username: request.user.sub,
        requestId,
        itemsCount: data.length,
        timestamp: new Date().toISOString(),
      });
      
      logger.info('Telemetria salva e Claim Check enviado para Kafka', {
        userId,
        requestId,
        itemsCount: data.length,
        totalSensors: data.reduce((sum, item) => sum + (item.sensor?.length || 0), 0),
        claimCheck: claimCheck.claim_check,
        fileSize: claimCheck.file_size,
      });
      
      // Responder imediatamente (202 Accepted)
      return reply.code(202).send({
        status: 'accepted',
        received: data.length,
        message: 'Dados recebidos e enviados para processamento',
        claim_check: claimCheck.claim_check, // Opcional: retornar claim check
      });
    } catch (error) {
      logger.error('Erro ao processar telemetria', {
        error: error.message,
        stack: error.stack,
        userId,
        requestId,
      });
      
      return reply.code(500).send({
        error: 'Erro ao processar dados de telemetria',
        message: error.message,
      });
    }
  });
};
