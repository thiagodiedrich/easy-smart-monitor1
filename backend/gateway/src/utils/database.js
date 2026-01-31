/**
 * Utilitário para consultas ao banco de dados.
 * 
 * Conecta ao PostgreSQL/TimescaleDB para executar queries.
 */
import pg from 'pg';
import { logger } from './logger.js';
import config from '../config.js';

const { Pool } = pg;

let pool = null;
const postgresDebug = (process.env.POSTGRES_DEBUG || 'false').toLowerCase() === 'true';

function redactRow(row) {
  if (!row || typeof row !== 'object') {
    return row;
  }
  const redacted = { ...row };
  const sensitiveKeys = [
    'hashed_password',
    'password',
    'refresh_token_hash',
    'refresh_token_expires_at',
    'secret',
  ];
  for (const key of sensitiveKeys) {
    if (key in redacted) {
      redacted[key] = '[REDACTED]';
    }
  }
  return redacted;
}

/**
 * Inicializa pool de conexões
 */
export function initDatabasePool() {
  if (!pool) {
    const connectionString = process.env.DATABASE_URL || 
      `postgresql://${process.env.POSTGRES_USER || 'easysmart'}:${process.env.POSTGRES_PASSWORD || 'easysmart_password'}@${process.env.POSTGRES_HOST || 'postgres'}:${process.env.POSTGRES_PORT || '5432'}/${process.env.POSTGRES_DB || 'easysmart_db'}`;
    
    pool = new Pool({
      connectionString,
      max: 20, // Máximo de conexões
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });
    
    pool.on('error', (err) => {
      logger.error('Erro inesperado no pool de conexões', { error: err.message });
    });
    
    logger.info('Pool de conexões PostgreSQL inicializado');
  }
  
  return pool;
}

/**
 * Executa query no banco de dados
 * 
 * @param {string} query - SQL query
 * @param {Array} params - Parâmetros da query
 * @returns {Promise<Array>} Resultados
 */
export async function queryDatabase(query, params = []) {
  if (!pool) {
    initDatabasePool();
  }
  
  const client = await pool.connect();
  
  try {
    const result = await client.query(query, params);
    if (postgresDebug) {
      logger.info('Postgres debug: query result', {
        query,
        params,
        rowCount: result?.rowCount ?? 0,
        rows: (result?.rows || []).map(redactRow),
      });
    }
    return result.rows;
  } catch (error) {
    logger.error('Erro ao executar query', {
      error: error.message,
      query: query.substring(0, 200) + '...'
    });
    throw error;
  } finally {
    client.release();
  }
}

/**
 * Fecha pool de conexões
 */
export async function closeDatabasePool() {
  if (pool) {
    await pool.end();
    pool = null;
    logger.info('Pool de conexões PostgreSQL fechado');
  }
}
