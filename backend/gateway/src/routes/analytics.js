/**
 * Rotas de Analytics - Consultas Otimizadas com Continuous Aggregates
 * 
 * Centraliza todas as regras de negócio para consultas analíticas.
 * Usa Continuous Aggregates do TimescaleDB para performance milissegundos.
 */
import { logger } from '../utils/logger.js';
import { queryDatabase } from '../utils/database.js';
import { hasPermission } from '../utils/permissions.js';
import config from '../config.js';

const errorResponseSchema = {
  type: 'object',
  properties: {
    error: { type: 'string' },
    message: { type: 'string' },
  },
};

function parseIntArrayOrNull(value) {
  if (value === undefined || value === null || value === '') {
    return null;
  }
  const raw = Array.isArray(value) ? value : String(value).split(',');
  const parsed = raw
    .map((item) => parseInt(String(item).trim(), 10))
    .filter((item) => !Number.isNaN(item));
  return parsed.length ? parsed : null;
}

function resolveTenantScope(request, reply) {
  const tenantId = request.user?.tenant_id || request.tenantContext?.tenantId || null;
  const organizationId = request.user?.organization_id || request.tenantContext?.organizationId || null;
  const workspaceId = request.user?.workspace_id || request.tenantContext?.workspaceId || null;
  const isSuper = tenantId !== null && Number(tenantId) === 0;
  const tenantFilter = parseIntArrayOrNull(request.query?.tenant_id);
  const organizationFilter = parseIntArrayOrNull(request.query?.organization_id);
  const workspaceFilter = parseIntArrayOrNull(request.query?.workspace_id);
  const hasFilters = Boolean(tenantFilter || organizationFilter || workspaceFilter);
  const effectiveTenant = isSuper && hasFilters ? (tenantFilter ?? null) : tenantId;
  const effectiveOrganization = isSuper && hasFilters ? organizationFilter : organizationId;
  const effectiveWorkspace = isSuper && hasFilters ? workspaceFilter : workspaceId;

  if (config.multiTenant.enabled && config.multiTenant.enforce && !tenantId) {
    reply.code(401).send({
      error: 'TENANT_REQUIRED',
      message: 'Tenant não informado',
    });
    return null;
  }
  const isSystemTenant = isSuper && !hasFilters;
  return {
    tenantId: effectiveTenant,
    organizationId: effectiveOrganization,
    workspaceId: effectiveWorkspace,
    isSystemTenant,
  };
}

function appendTenantFilters(scope, params, tableAlias = 'e') {
  if (!scope) {
    return '';
  }
  if (scope.isSystemTenant) {
    return '';
  }

  const clauses = [];
  if (scope.tenantId) {
    if (Array.isArray(scope.tenantId)) {
      if (!scope.tenantId.includes(0)) {
        clauses.push(`${tableAlias}.tenant_id = ANY($${params.length + 1})`);
        params.push(scope.tenantId);
      }
    } else {
      clauses.push(`${tableAlias}.tenant_id = $${params.length + 1}`);
      params.push(scope.tenantId);
    }
  }
  if (scope.organizationId) {
    if (Array.isArray(scope.organizationId)) {
      if (!scope.organizationId.includes(0)) {
        clauses.push(`${tableAlias}.organization_id = ANY($${params.length + 1})`);
        params.push(scope.organizationId);
      }
    } else {
      if (Number(scope.organizationId) !== 0) {
        clauses.push(`${tableAlias}.organization_id = $${params.length + 1}`);
        params.push(scope.organizationId);
      }
    }
  }
  if (scope.workspaceId) {
    if (Array.isArray(scope.workspaceId)) {
      if (!scope.workspaceId.includes(0)) {
        clauses.push(`${tableAlias}.workspace_id = ANY($${params.length + 1})`);
        params.push(scope.workspaceId);
      }
    } else {
      if (Number(scope.workspaceId) !== 0) {
        clauses.push(`${tableAlias}.workspace_id = $${params.length + 1}`);
        params.push(scope.workspaceId);
      }
    }
  }

  return clauses.length ? ` AND ${clauses.join(' AND ')}` : '';
}

/**
 * GET /api/v1/analytics/equipment/:equipmentUuid/history
 * 
 * Retorna histórico de telemetria de um equipamento.
 * Usa continuous aggregates para performance otimizada.
 * 
 * Query params:
 * - period: 'hour' | 'day' | 'raw' (default: 'hour')
 * - start_date: ISO 8601 (default: 7 dias atrás)
 * - end_date: ISO 8601 (default: agora)
 * - sensor_type: Filtrar por tipo de sensor (opcional)
 */
export async function getEquipmentHistory(request, reply) {
  try {
    const { equipmentUuid } = request.params;
    const { 
      period = 'hour',
      start_date,
      end_date,
      sensor_type 
    } = request.query;
    
    // Validação de período
    if (!['hour', 'day', 'raw'].includes(period)) {
      return reply.code(400).send({
        error: 'Invalid period',
        message: 'Period must be: hour, day, or raw'
      });
    }
    
    // Calcular datas padrão
    const endDate = end_date ? new Date(end_date) : new Date();
    const startDate = start_date 
      ? new Date(start_date) 
      : new Date(Date.now() - 7 * 24 * 60 * 60 * 1000); // 7 dias atrás
    
    // Validar datas
    if (startDate >= endDate) {
      return reply.code(400).send({
        error: 'Invalid date range',
        message: 'start_date must be before end_date'
      });
    }

    const scope = resolveTenantScope(request, reply);
    if (!scope) {
      return;
    }
    
    // Escolher view baseada no período
    let viewName, timeColumn;
    if (period === 'hour') {
      viewName = 'telemetry_hourly';
      timeColumn = 'bucket';
    } else if (period === 'day') {
      viewName = 'telemetry_daily';
      timeColumn = 'bucket';
    } else {
      // Raw data (últimos 30 dias apenas, devido à retenção)
      viewName = 'telemetry_data';
      timeColumn = 'timestamp';
    }
    
    // Construir query otimizada
    let query = `
      SELECT 
        ${timeColumn} AS time,
        s.uuid AS sensor_uuid,
        s.name AS sensor_name,
        s.type AS sensor_type,
        s.unit AS sensor_unit,
        ${period === 'raw' 
          ? 'td.value, td.status, td.metadata' 
          : 'agg.avg_value, agg.max_value, agg.min_value, agg.sample_count, agg.active_minutes, agg.median_value, agg.p95_value'
        }
      FROM ${viewName} ${period === 'raw' ? 'td' : 'agg'}
      INNER JOIN sensors s ON ${period === 'raw' ? 'td.sensor_id' : 'agg.sensor_id'} = s.id
      INNER JOIN equipments e ON ${period === 'raw' ? 'td.equipment_id' : 'agg.equipment_id'} = e.id
      WHERE e.uuid = $1
        AND ${timeColumn} >= $2
        AND ${timeColumn} <= $3
    `;
    
    const params = [equipmentUuid, startDate.toISOString(), endDate.toISOString()];
    query += appendTenantFilters(scope, params, 'e');
    
    // Filtrar por tipo de sensor se especificado
    if (sensor_type) {
      query += ` AND s.type = $${params.length + 1}`;
      params.push(sensor_type);
    }
    
    query += ` ORDER BY ${timeColumn} ASC, s.type ASC`;
    
    // Executar query
    const result = await queryDatabase(query, params);
    
    logger.info('Histórico de equipamento consultado', {
      equipmentUuid,
      period,
      startDate: startDate.toISOString(),
      endDate: endDate.toISOString(),
      rows: result.length,
      view: viewName,
      tenantId: scope.tenantId,
      organizationId: scope.organizationId,
      workspaceId: scope.workspaceId,
    });
    
    return reply.send({
      equipment_uuid: equipmentUuid,
      period,
      start_date: startDate.toISOString(),
      end_date: endDate.toISOString(),
      data: result
    });
    
  } catch (error) {
    logger.error('Erro ao consultar histórico', {
      error: error.message,
      stack: error.stack
    });
    
    return reply.code(500).send({
      error: 'Internal server error',
      message: error.message
    });
  }
}

/**
 * GET /api/v1/analytics/sensor/:sensorUuid/history
 * 
 * Retorna histórico de um sensor específico.
 */
export async function getSensorHistory(request, reply) {
  try {
    const { sensorUuid } = request.params;
    const { 
      period = 'hour',
      start_date,
      end_date
    } = request.query;
    
    // Validação e cálculo de datas (mesmo padrão acima)
    if (!['hour', 'day', 'raw'].includes(period)) {
      return reply.code(400).send({
        error: 'Invalid period',
        message: 'Period must be: hour, day, or raw'
      });
    }
    
    const endDate = end_date ? new Date(end_date) : new Date();
    const startDate = start_date 
      ? new Date(start_date) 
      : new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    
    if (startDate >= endDate) {
      return reply.code(400).send({
        error: 'Invalid date range',
        message: 'start_date must be before end_date'
      });
    }

    const scope = resolveTenantScope(request, reply);
    if (!scope) {
      return;
    }
    
    // Escolher view
    let viewName, timeColumn;
    if (period === 'hour') {
      viewName = 'telemetry_hourly';
      timeColumn = 'bucket';
    } else if (period === 'day') {
      viewName = 'telemetry_daily';
      timeColumn = 'bucket';
    } else {
      viewName = 'telemetry_data';
      timeColumn = 'timestamp';
    }
    
    // Query otimizada
    let query = `
      SELECT 
        ${timeColumn} AS time,
        ${period === 'raw' 
          ? 'td.value, td.status, td.metadata' 
          : 'agg.avg_value, agg.max_value, agg.min_value, agg.sample_count, agg.active_minutes, agg.median_value, agg.p95_value'
        }
      FROM ${viewName} ${period === 'raw' ? 'td' : 'agg'}
      INNER JOIN sensors s ON ${period === 'raw' ? 'td.sensor_id' : 'agg.sensor_id'} = s.id
      INNER JOIN equipments e ON ${period === 'raw' ? 'td.equipment_id' : 'agg.equipment_id'} = e.id
      WHERE s.uuid = $1
        AND ${timeColumn} >= $2
        AND ${timeColumn} <= $3
    `;
    const params = [sensorUuid, startDate.toISOString(), endDate.toISOString()];
    query += appendTenantFilters(scope, params, 'e');
    query += ` ORDER BY ${timeColumn} ASC`;
    
    const result = await queryDatabase(query, params);
    
    logger.info('Histórico de sensor consultado', {
      sensorUuid,
      period,
      rows: result.length,
      tenantId: scope.tenantId,
      organizationId: scope.organizationId,
      workspaceId: scope.workspaceId,
    });
    
    return reply.send({
      sensor_uuid: sensorUuid,
      period,
      start_date: startDate.toISOString(),
      end_date: endDate.toISOString(),
      data: result
    });
    
  } catch (error) {
    logger.error('Erro ao consultar histórico de sensor', {
      error: error.message
    });
    
    return reply.code(500).send({
      error: 'Internal server error',
      message: error.message
    });
  }
}

/**
 * GET /api/v1/analytics/equipment/:equipmentUuid/stats
 * 
 * Retorna estatísticas agregadas de um equipamento.
 * Otimizado para dashboards.
 */
export async function getEquipmentStats(request, reply) {
  try {
    const { equipmentUuid } = request.params;
    const { 
      period = '24h', // 24h, 7d, 30d, 1y
      sensor_type
    } = request.query;
    
    // Calcular intervalo baseado no período
    let interval, viewName, timeColumn;
    const now = new Date();
    
    switch (period) {
      case '24h':
        interval = { days: 1 };
        viewName = 'telemetry_hourly';
        timeColumn = 'bucket';
        break;
      case '7d':
        interval = { days: 7 };
        viewName = 'telemetry_daily';
        timeColumn = 'bucket';
        break;
      case '30d':
        interval = { days: 30 };
        viewName = 'telemetry_daily';
        timeColumn = 'bucket';
        break;
      case '1y':
        interval = { days: 365 };
        viewName = 'telemetry_daily';
        timeColumn = 'bucket';
        break;
      default:
        return reply.code(400).send({
          error: 'Invalid period',
          message: 'Period must be: 24h, 7d, 30d, or 1y'
        });
    }
    
    const startDate = new Date(now.getTime() - interval.days * 24 * 60 * 60 * 1000);

    const scope = resolveTenantScope(request, reply);
    if (!scope) {
      return;
    }
    
    // Query agregada por sensor
    let query = `
      SELECT 
        s.uuid AS sensor_uuid,
        s.name AS sensor_name,
        s.type AS sensor_type,
        s.unit AS sensor_unit,
        AVG(agg.avg_value) AS overall_avg,
        MAX(agg.max_value) AS overall_max,
        MIN(agg.min_value) AS overall_min,
        SUM(agg.sample_count) AS total_samples,
        COUNT(DISTINCT agg.bucket) AS active_periods
      FROM ${viewName} agg
      INNER JOIN sensors s ON agg.sensor_id = s.id
      INNER JOIN equipments e ON agg.equipment_id = e.id
      WHERE e.uuid = $1
        AND agg.${timeColumn} >= $2
    `;
    
    const params = [equipmentUuid, startDate.toISOString()];
    query += appendTenantFilters(scope, params, 'e');
    
    if (sensor_type) {
      query += ` AND s.type = $${params.length + 1}`;
      params.push(sensor_type);
    }
    
    query += ` GROUP BY s.uuid, s.name, s.type, s.unit ORDER BY s.type, s.name`;
    
    const result = await queryDatabase(query, params);
    
    logger.info('Estatísticas de equipamento consultadas', {
      equipmentUuid,
      period,
      sensors: result.length,
      tenantId: scope.tenantId,
      organizationId: scope.organizationId,
      workspaceId: scope.workspaceId,
    });
    
    return reply.send({
      equipment_uuid: equipmentUuid,
      period,
      start_date: startDate.toISOString(),
      end_date: now.toISOString(),
      sensors: result
    });
    
  } catch (error) {
    logger.error('Erro ao consultar estatísticas', {
      error: error.message
    });
    
    return reply.code(500).send({
      error: 'Internal server error',
      message: error.message
    });
  }
}

/**
 * GET /api/v1/analytics/home-assistant/:equipmentUuid
 * 
 * Endpoint otimizado para integração Home Assistant.
 * Retorna dados no formato esperado pelo Home Assistant.
 */
export async function getHomeAssistantData(request, reply) {
  try {
    const { equipmentUuid } = request.params;
    const { 
      hours = 24, // Últimas N horas
      sensor_type
    } = request.query;
    
    const hoursInt = parseInt(hours, 10);
    if (isNaN(hoursInt) || hoursInt < 1 || hoursInt > 168) {
      return reply.code(400).send({
        error: 'Invalid hours',
        message: 'Hours must be between 1 and 168 (7 days)'
      });
    }
    
    const startDate = new Date(Date.now() - hoursInt * 60 * 60 * 1000);

    const scope = resolveTenantScope(request, reply);
    if (!scope) {
      return;
    }
    
    // Query otimizada para Home Assistant
    // Retorna dados horários (balance entre granularidade e performance)
    let query = `
      SELECT 
        agg.bucket AS time,
        s.uuid AS sensor_uuid,
        s.name AS sensor_name,
        s.type AS sensor_type,
        s.unit AS sensor_unit,
        agg.avg_value AS value,
        agg.max_value,
        agg.min_value,
        agg.sample_count
      FROM telemetry_hourly agg
      INNER JOIN sensors s ON agg.sensor_id = s.id
      INNER JOIN equipments e ON agg.equipment_id = e.id
      WHERE e.uuid = $1
        AND agg.bucket >= $2
    `;
    
    const params = [equipmentUuid, startDate.toISOString()];
    query += appendTenantFilters(scope, params, 'e');
    
    if (sensor_type) {
      query += ` AND s.type = $${params.length + 1}`;
      params.push(sensor_type);
    }
    
    query += ` ORDER BY agg.bucket ASC, s.type ASC`;
    
    const result = await queryDatabase(query, params);
    
    // Formatar para Home Assistant
    const formatted = result.map(row => ({
      time: row.time,
      sensor_uuid: row.sensor_uuid,
      sensor_name: row.sensor_name,
      sensor_type: row.sensor_type,
      unit: row.sensor_unit,
      value: row.value,
      max: row.max_value,
      min: row.min_value,
      samples: row.sample_count
    }));
    
    logger.info('Dados Home Assistant consultados', {
      equipmentUuid,
      hours: hoursInt,
      rows: formatted.length,
      tenantId: scope.tenantId,
      organizationId: scope.organizationId,
      workspaceId: scope.workspaceId,
    });
    
    return reply.send({
      equipment_uuid: equipmentUuid,
      period_hours: hoursInt,
      data: formatted
    });
    
  } catch (error) {
    logger.error('Erro ao consultar dados Home Assistant', {
      error: error.message
    });
    
    return reply.code(500).send({
      error: 'Internal server error',
      message: error.message
    });
  }
}

/**
 * Registra rotas de analytics
 */
export async function analyticsRoutes(fastify, options) {
  // Middleware de autenticação (apenas frontend pode acessar analytics)
  fastify.addHook('onRequest', async (request, reply) => {
    try {
      await request.jwtVerify();
      
      // Verificar se é frontend
      if (request.user.user_type !== 'frontend') {
        logger.warn('Tentativa de acessar analytics com token não-frontend', {
          user_type: request.user.user_type,
          username: request.user.sub,
        });
        return reply.code(403).send({ 
          error: 'FORBIDDEN',
          message: 'Apenas usuários frontend podem acessar analytics' 
        });
      }
      if (!hasPermission(request, 'analytics.read')) {
        return reply.code(403).send({
          error: 'FORBIDDEN',
          message: 'Acesso restrito pelo role',
        });
      }
    } catch (err) {
      return reply.code(401).send({ 
        error: 'UNAUTHORIZED',
        message: 'Não autorizado' 
      });
    }
  });
  
  // Histórico de equipamento
  fastify.get('/analytics/equipment/:equipmentUuid/history', {
    schema: {
      description: 'Histórico de telemetria por equipamento',
      tags: ['Analytics'],
      params: {
        type: 'object',
        properties: {
          equipmentUuid: { type: 'string', format: 'uuid' }
        },
        required: ['equipmentUuid']
      },
      querystring: {
        type: 'object',
        properties: {
          tenant_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          organization_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          workspace_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          period: { type: 'string', enum: ['hour', 'day', 'raw'] },
          start_date: { type: 'string', format: 'date-time' },
          end_date: { type: 'string', format: 'date-time' },
          sensor_type: { type: 'string' }
        }
      },
      response: {
        200: {
          type: 'object',
          properties: {
            equipment_uuid: { type: 'string', description: 'UUID do equipamento' },
            period: { type: 'string', description: 'Granularidade' },
            start_date: { type: 'string', description: 'Data inicial (ISO)' },
            end_date: { type: 'string', description: 'Data final (ISO)' },
            data: {
              type: 'array',
              items: { type: 'object', additionalProperties: true },
              description: 'Séries por sensor/tempo',
            },
          },
          additionalProperties: true,
        },
        400: errorResponseSchema,
        401: errorResponseSchema,
        403: errorResponseSchema,
        500: errorResponseSchema,
      }
    }
  }, getEquipmentHistory);
  
  // Histórico de sensor
  fastify.get('/analytics/sensor/:sensorUuid/history', {
    schema: {
      description: 'Histórico de telemetria por sensor',
      tags: ['Analytics'],
      params: {
        type: 'object',
        properties: {
          sensorUuid: { type: 'string', format: 'uuid' }
        },
        required: ['sensorUuid']
      },
      querystring: {
        type: 'object',
        properties: {
          tenant_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          organization_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          workspace_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          period: { type: 'string', enum: ['hour', 'day', 'raw'] },
          start_date: { type: 'string', format: 'date-time' },
          end_date: { type: 'string', format: 'date-time' }
        }
      },
      response: {
        200: {
          type: 'object',
          properties: {
            sensor_uuid: { type: 'string', description: 'UUID do sensor' },
            period: { type: 'string', description: 'Granularidade' },
            start_date: { type: 'string', description: 'Data inicial (ISO)' },
            end_date: { type: 'string', description: 'Data final (ISO)' },
            data: {
              type: 'array',
              items: { type: 'object', additionalProperties: true },
              description: 'Série temporal do sensor',
            },
          },
          additionalProperties: true,
        },
        400: errorResponseSchema,
        401: errorResponseSchema,
        403: errorResponseSchema,
        500: errorResponseSchema,
      }
    }
  }, getSensorHistory);
  
  // Estatísticas de equipamento
  fastify.get('/analytics/equipment/:equipmentUuid/stats', {
    schema: {
      description: 'Estatísticas agregadas do equipamento',
      tags: ['Analytics'],
      params: {
        type: 'object',
        properties: {
          equipmentUuid: { type: 'string', format: 'uuid' }
        },
        required: ['equipmentUuid']
      },
      querystring: {
        type: 'object',
        properties: {
          tenant_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          organization_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          workspace_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          period: { type: 'string', enum: ['24h', '7d', '30d', '1y'] },
          sensor_type: { type: 'string' }
        }
      },
      response: {
        200: {
          type: 'object',
          properties: {
            equipment_uuid: { type: 'string', description: 'UUID do equipamento' },
            period: { type: 'string', description: 'Janela de agregação' },
            start_date: { type: 'string', description: 'Data inicial (ISO)' },
            end_date: { type: 'string', description: 'Data final (ISO)' },
            sensors: {
              type: 'array',
              items: { type: 'object', additionalProperties: true },
              description: 'Estatísticas por sensor',
            },
          },
          additionalProperties: true,
        },
        400: errorResponseSchema,
        401: errorResponseSchema,
        403: errorResponseSchema,
        500: errorResponseSchema,
      }
    }
  }, getEquipmentStats);
  
  // Dados para Home Assistant
  fastify.get('/analytics/home-assistant/:equipmentUuid', {
    schema: {
      description: 'Dados para integração Home Assistant',
      tags: ['Analytics'],
      params: {
        type: 'object',
        properties: {
          equipmentUuid: { type: 'string', format: 'uuid' }
        },
        required: ['equipmentUuid']
      },
      querystring: {
        type: 'object',
        properties: {
          tenant_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          organization_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          workspace_id: { anyOf: [{ type: 'number', minimum: 0 }, { type: 'string' }, { type: 'array', items: { type: 'number' } }] },
          hours: { type: 'integer', minimum: 1, maximum: 168 },
          sensor_type: { type: 'string' }
        }
      },
      response: {
        200: {
          type: 'object',
          properties: {
            equipment_uuid: { type: 'string', description: 'UUID do equipamento' },
            period_hours: { type: 'number', description: 'Janela em horas' },
            data: {
              type: 'array',
              items: { type: 'object', additionalProperties: true },
              description: 'Formato compatível com Home Assistant',
            },
          },
          additionalProperties: true,
        },
        400: errorResponseSchema,
        401: errorResponseSchema,
        403: errorResponseSchema,
        500: errorResponseSchema,
      }
    }
  }, getHomeAssistantData);
}
