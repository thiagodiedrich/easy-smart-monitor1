/**
 * Rotas de Analytics - Consultas Otimizadas com Continuous Aggregates
 * 
 * Centraliza todas as regras de negócio para consultas analíticas.
 * Usa Continuous Aggregates do TimescaleDB para performance milissegundos.
 */
import { logger } from '../utils/logger.js';
import { queryDatabase } from '../utils/database.js';

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
      view: viewName
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
    const query = `
      SELECT 
        ${timeColumn} AS time,
        ${period === 'raw' 
          ? 'td.value, td.status, td.metadata' 
          : 'agg.avg_value, agg.max_value, agg.min_value, agg.sample_count, agg.active_minutes, agg.median_value, agg.p95_value'
        }
      FROM ${viewName} ${period === 'raw' ? 'td' : 'agg'}
      INNER JOIN sensors s ON ${period === 'raw' ? 'td.sensor_id' : 'agg.sensor_id'} = s.id
      WHERE s.uuid = $1
        AND ${timeColumn} >= $2
        AND ${timeColumn} <= $3
      ORDER BY ${timeColumn} ASC
    `;
    
    const result = await queryDatabase(query, [
      sensorUuid,
      startDate.toISOString(),
      endDate.toISOString()
    ]);
    
    logger.info('Histórico de sensor consultado', {
      sensorUuid,
      period,
      rows: result.length
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
    
    if (sensor_type) {
      query += ` AND s.type = $${params.length + 1}`;
      params.push(sensor_type);
    }
    
    query += ` GROUP BY s.uuid, s.name, s.type, s.unit ORDER BY s.type, s.name`;
    
    const result = await queryDatabase(query, params);
    
    logger.info('Estatísticas de equipamento consultadas', {
      equipmentUuid,
      period,
      sensors: result.length
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
      rows: formatted.length
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
  // Histórico de equipamento
  fastify.get('/analytics/equipment/:equipmentUuid/history', {
    preHandler: [fastify.authenticate],
    schema: {
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
          period: { type: 'string', enum: ['hour', 'day', 'raw'] },
          start_date: { type: 'string', format: 'date-time' },
          end_date: { type: 'string', format: 'date-time' },
          sensor_type: { type: 'string' }
        }
      }
    }
  }, getEquipmentHistory);
  
  // Histórico de sensor
  fastify.get('/analytics/sensor/:sensorUuid/history', {
    preHandler: [fastify.authenticate],
    schema: {
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
          period: { type: 'string', enum: ['hour', 'day', 'raw'] },
          start_date: { type: 'string', format: 'date-time' },
          end_date: { type: 'string', format: 'date-time' }
        }
      }
    }
  }, getSensorHistory);
  
  // Estatísticas de equipamento
  fastify.get('/analytics/equipment/:equipmentUuid/stats', {
    preHandler: [fastify.authenticate],
    schema: {
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
          period: { type: 'string', enum: ['24h', '7d', '30d', '1y'] },
          sensor_type: { type: 'string' }
        }
      }
    }
  }, getEquipmentStats);
  
  // Dados para Home Assistant
  fastify.get('/analytics/home-assistant/:equipmentUuid', {
    preHandler: [fastify.authenticate],
    schema: {
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
          hours: { type: 'integer', minimum: 1, maximum: 168 },
          sensor_type: { type: 'string' }
        }
      }
    }
  }, getHomeAssistantData);
}
