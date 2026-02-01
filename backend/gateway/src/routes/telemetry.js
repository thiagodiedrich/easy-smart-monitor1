/**
 * Rotas de Telemetria
 * 
 * Recebe dados de telemetria, salva em Object Storage e envia Claim Check para Kafka.
 * Implementa Claim Check Pattern para payloads grandes.
 */
import { sendTelemetryToKafka } from '../kafka/producer.js';
import { saveTelemetryToStorage } from '../storage/storage.js';
import { logger } from '../utils/logger.js';
import { queryDatabase } from '../utils/database.js';
import config from '../config.js';

const errorResponseSchema = {
  type: 'object',
  properties: {
    error: {
      type: 'string',
      enum: [
        'UNAUTHORIZED',
        'FORBIDDEN',
        'QUOTA_EXCEEDED',
        'INVALID_SCOPE',
        'INVALID_PAYLOAD',
      ],
    },
    message: { type: 'string' },
  },
};

async function getTenantQuota(tenantId) {
  const result = await queryDatabase(
    `
      SELECT
        COALESCE(tl.items_per_day, p.items_per_day) AS items_per_day,
        COALESCE(tl.sensors_per_day, p.sensors_per_day) AS sensors_per_day,
        COALESCE(tl.bytes_per_day, p.bytes_per_day) AS bytes_per_day
      FROM tenants t
      LEFT JOIN plans p ON p.code = t.plan_code
      LEFT JOIN tenant_limits tl ON tl.tenant_id = t.id
      WHERE t.id = $1
    `,
    [tenantId]
  );
  return result?.[0] || null;
}

async function getTenantUsageToday(tenantId) {
  const result = await queryDatabase(
    `
      SELECT items_count, sensors_count, bytes_ingested
      FROM tenant_usage_daily
      WHERE tenant_id = $1 AND day = CURRENT_DATE
    `,
    [tenantId]
  );
  return result?.[0] || { items_count: 0, sensors_count: 0, bytes_ingested: 0 };
}

function estimatePayloadBytes(data) {
  try {
    return Buffer.byteLength(JSON.stringify(data), 'utf8');
  } catch {
    return 0;
  }
}

function resolveScopeValue(headerValue, claimValue) {
  if (headerValue !== undefined && headerValue !== null && headerValue !== '') {
    const parsed = parseInt(headerValue, 10);
    return Number.isNaN(parsed) ? 0 : parsed;
  }
  if (Array.isArray(claimValue)) {
    if (claimValue.includes(0)) {
      return 0;
    }
    return claimValue[0];
  }
  return claimValue ?? 0;
}

export const telemetryRoutes = async (fastify) => {
  // Middleware de autenticação (apenas devices podem enviar telemetria)
  fastify.addHook('onRequest', async (request, reply) => {
    try {
      await request.jwtVerify();
      
      // Verificar se é dispositivo
      if (request.user.user_type !== 'device') {
        logger.warn('Tentativa de enviar telemetria com token não-device', {
          user_type: request.user.user_type,
          username: request.user.sub,
        });
        return reply.code(403).send({ 
          error: 'FORBIDDEN',
          message: 'Apenas dispositivos podem enviar telemetria' 
        });
      }
    } catch (err) {
      return reply.code(401).send({ 
        error: 'UNAUTHORIZED',
        message: 'Não autorizado' 
      });
    }
  });
  
  // Aplicar Shield (rate limiting + concurrency lock)
  fastify.addHook('preHandler', async (request, reply) => {
    if (fastify.shieldRequest) {
      await fastify.shieldRequest(request, reply);
    }
    if (fastify.preventConcurrency) {
      await fastify.preventConcurrency(request, reply);
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
            equip_uuid: { type: 'string', description: 'Ex: 550e8400-e29b-41d4-a716-446655440000' },
            equip_nome: { type: 'string', description: 'Ex: Gerador A' },
            equip_local: { type: 'string', description: 'Ex: Sala 1' },
            equip_status: { type: 'string', description: 'Ex: ativo' },
            equip_intervalo_coleta: { type: 'number', description: 'Ex: 60' },
            equip_sirene_ativa: { type: 'string', description: 'Ex: true' },
            equip_sirete_tempo: { type: 'number', description: 'Ex: 10' },
            sensor: {
              type: 'array',
              items: { 
                type: 'object',
                properties: {
                  sensor_uuid: { type: 'string', description: 'Ex: 550e8400-e29b-41d4-a716-446655440001' },
                  sensor_nome: { type: 'string', description: 'Ex: Temperatura' },
                  sensor_tipo: { type: 'string', description: 'Ex: temp' },
                  sensor_telemetria: { type: ['string', 'number'], description: 'Ex: 26.5' },
                  sensor_datahora_coleta: { type: 'string', description: 'Ex: 2026-02-01T03:00:00Z' },
                  valor: { type: ['number', 'null'], description: 'Ex: 26.5' },
                  status: { type: ['string', 'null'], description: 'Ex: active' },
                  timestamp: { type: 'string', description: 'Ex: 2026-02-01T03:00:00Z' },
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
            claim_check: { type: 'string' },
          },
        },
        400: errorResponseSchema,
        401: errorResponseSchema,
        403: errorResponseSchema,
        429: errorResponseSchema,
        500: errorResponseSchema,
      },
    },
  }, async (request, reply) => {
    const { body: data } = request;
    const userId = request.user.sub; // Do JWT
    const requestId = request.id;
    const tenantId = request.user.tenant_id || request.tenantContext?.tenantId;
    const organizationId = resolveScopeValue(
      request.headers?.[config.multiTenant.organizationHeader],
      request.user.organization_id || request.tenantContext?.organizationId
    );
    const workspaceId = resolveScopeValue(
      request.headers?.[config.multiTenant.workspaceHeader],
      request.user.workspace_id || request.tenantContext?.workspaceId
    );
    const totalSensors = data.reduce((sum, item) => sum + (item.sensor?.length || 0), 0);
    
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

    if (!tenantId) {
      return reply.code(400).send({
        error: 'tenant_id obrigatório para telemetria',
      });
    }
    if (!organizationId) {
      return reply.code(400).send({
        error: 'organization_id obrigatório para telemetria',
      });
    }
    if (!workspaceId) {
      return reply.code(400).send({
        error: 'workspace_id obrigatório para telemetria',
      });
    }

    // Quotas por tenant (Fase 5)
    if (config.quota.enabled && config.quota.enforce && tenantId) {
      const quota = await getTenantQuota(tenantId);
      if (quota) {
        const usage = await getTenantUsageToday(tenantId);
        const payloadBytes = quota.bytes_per_day
          ? (config.quota.estimateBytes ? estimatePayloadBytes(data) : 0)
          : 0;
        const projectedItems = Number(usage.items_count || 0) + data.length;
        const projectedSensors = Number(usage.sensors_count || 0) + totalSensors;
        const projectedBytes = Number(usage.bytes_ingested || 0) + payloadBytes;

        if (quota.items_per_day && projectedItems > Number(quota.items_per_day)) {
          if (config.billing.eventsEnabled) {
            try {
              await queryDatabase(
                `
                  INSERT INTO tenant_billing_events (tenant_id, event_type, message, metadata)
                  VALUES ($1, $2, $3, $4)
                `,
                [
                  tenantId,
                  'quota_exceeded',
                  'Limite diário de itens excedido',
                  { items_per_day: quota.items_per_day, projected_items: projectedItems },
                ]
              );
            } catch (err) {
              logger.warn('Falha ao registrar billing event', { error: err.message });
            }
          }
          return reply.code(429).send({
            error: 'QUOTA_EXCEEDED',
            message: 'Limite diário de itens excedido',
          });
        }
        if (quota.sensors_per_day && projectedSensors > Number(quota.sensors_per_day)) {
          if (config.billing.eventsEnabled) {
            try {
              await queryDatabase(
                `
                  INSERT INTO tenant_billing_events (tenant_id, event_type, message, metadata)
                  VALUES ($1, $2, $3, $4)
                `,
                [
                  tenantId,
                  'quota_exceeded',
                  'Limite diário de sensores excedido',
                  { sensors_per_day: quota.sensors_per_day, projected_sensors: projectedSensors },
                ]
              );
            } catch (err) {
              logger.warn('Falha ao registrar billing event', { error: err.message });
            }
          }
          return reply.code(429).send({
            error: 'QUOTA_EXCEEDED',
            message: 'Limite diário de sensores excedido',
          });
        }
        if (quota.bytes_per_day && projectedBytes > Number(quota.bytes_per_day)) {
          if (config.billing.eventsEnabled) {
            try {
              await queryDatabase(
                `
                  INSERT INTO tenant_billing_events (tenant_id, event_type, message, metadata)
                  VALUES ($1, $2, $3, $4)
                `,
                [
                  tenantId,
                  'quota_exceeded',
                  'Limite diário de bytes excedido',
                  { bytes_per_day: quota.bytes_per_day, projected_bytes: projectedBytes },
                ]
              );
            } catch (err) {
              logger.warn('Falha ao registrar billing event', { error: err.message });
            }
          }
          return reply.code(429).send({
            error: 'QUOTA_EXCEEDED',
            message: 'Limite diário de bytes excedido',
          });
        }
      }
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
        tenantId,
        organizationId,
        workspaceId,
        requestId,
        itemsCount: data.length,
      });
      
      // Enviar apenas Claim Check (referência) para Kafka (não bloqueia)
      await sendTelemetryToKafka(claimCheck, {
        userId,
        username: request.user.sub,
        tenantId,
        organizationId,
        workspaceId,
        requestId,
        itemsCount: data.length,
        totalSensors,
        fileSize: claimCheck.file_size,
        timestamp: new Date().toISOString(),
      });
      
      logger.info('Telemetria salva e Claim Check enviado para Kafka', {
        userId,
        requestId,
        itemsCount: data.length,
        totalSensors,
        tenantId,
        organizationId,
        workspaceId,
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
        tenantId,
        organizationId,
        workspaceId,
      });
      
      return reply.code(500).send({
        error: 'Erro ao processar dados de telemetria',
        message: error.message,
      });
    }
  });
};
