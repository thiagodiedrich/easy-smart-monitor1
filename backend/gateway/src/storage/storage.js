/**
 * Storage Service - Claim Check Pattern
 * 
 * Gerencia salvamento de arquivos em Object Storage (MinIO/S3).
 * Usa streaming para payloads grandes sem consumir memória excessiva.
 */
import { Client } from 'minio';
import { randomUUID } from 'crypto';
import { gzipSync, gunzipSync } from 'zlib';
import { logger } from '../utils/logger.js';
import config from '../config.js';

let minioClient = null;

/**
 * Inicializa cliente MinIO
 */
export function initStorage() {
  if (config.storage.type === 'minio' || !config.storage.type) {
    minioClient = new Client({
      endPoint: config.storage.endpoint,
      port: parseInt(config.storage.port || '9000', 10),
      useSSL: config.storage.useSSL === 'true',
      accessKey: config.storage.accessKey,
      secretKey: config.storage.secretKey,
    });
    
    // Garantir que bucket existe
    ensureBucket().catch((err) => {
      logger.error('Erro ao criar bucket', { error: err.message });
    });
    
    logger.info('Storage MinIO inicializado', {
      endpoint: config.storage.endpoint,
      bucket: config.storage.bucket,
    });
  } else if (config.storage.type === 'local') {
    // Storage local (filesystem)
    logger.info('Storage local inicializado', {
      path: config.storage.localPath,
    });
  }
}

/**
 * Garante que o bucket existe
 */
async function ensureBucket() {
  if (!minioClient) return;
  
  try {
    const bucketExists = await minioClient.bucketExists(config.storage.bucket);
    
    if (!bucketExists) {
      await minioClient.makeBucket(config.storage.bucket, config.storage.region || 'us-east-1');
      logger.info('Bucket criado', { bucket: config.storage.bucket });
    }
  } catch (error) {
    logger.error('Erro ao verificar/criar bucket', { error: error.message });
  }
}

/**
 * Salva dados de telemetria em Object Storage
 * 
 * @param {Array|Object} data - Dados de telemetria
 * @param {Object} metadata - Metadados (userId, requestId, etc.)
 * @returns {Promise<Object>} Claim Check com referência ao arquivo
 */
export async function saveTelemetryToStorage(data, metadata = {}) {
  const startTime = Date.now();
  
  try {
    // Gerar nome único do arquivo
    const fileId = randomUUID();
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const fileName = `telemetry/${timestamp}/${fileId}.json.gz`;
    
    // Serializar dados
    const jsonData = JSON.stringify(data);
    const jsonBuffer = Buffer.from(jsonData, 'utf-8');
    const originalSize = jsonBuffer.length;
    
    // Comprimir com GZIP
    const compressedBuffer = gzipSync(jsonBuffer, { level: 6 });
    const fileSize = compressedBuffer.length;
    
    if (config.storage.type === 'minio' || !config.storage.type) {
      // Upload para MinIO
      await minioClient.putObject(
        config.storage.bucket,
        fileName,
        compressedBuffer,
        fileSize,
        {
          'Content-Type': 'application/json',
          'Content-Encoding': 'gzip',
          'X-User-Id': (metadata.userId || metadata.username || '').toString(),
          'X-Request-Id': metadata.requestId || '',
        }
      );
    } else if (config.storage.type === 'local') {
      // Storage local (filesystem)
      const fs = await import('fs/promises');
      const path = await import('path');
      
      const storagePath = config.storage.localPath || '/app/storage';
      const fullPath = path.join(storagePath, fileName);
      const dirPath = path.dirname(fullPath);
      
      // Criar diretório se não existir
      await fs.mkdir(dirPath, { recursive: true });
      
      // Salvar arquivo
      await fs.writeFile(fullPath, compressedBuffer);
    }
    
    const duration = Date.now() - startTime;
    const compressionRatio = ((1 - fileSize / originalSize) * 100).toFixed(1);
    
    logger.info('Telemetria salva em storage', {
      fileName,
      fileSize,
      originalSize,
      compressionRatio: `${compressionRatio}%`,
      duration: `${duration}ms`,
      userId: metadata.userId || metadata.username,
    });
    
    // Retornar Claim Check
    return {
      claim_check: fileName,
      storage_type: config.storage.type || 'minio',
      storage_endpoint: config.storage.endpoint,
      bucket: config.storage.bucket,
      file_size: fileSize,
      original_size: originalSize,
      compression: 'gzip',
      timestamp: new Date().toISOString(),
    };
    
  } catch (error) {
    logger.error('Erro ao salvar telemetria em storage', {
      error: error.message,
      stack: error.stack,
    });
    throw error;
  }
}

/**
 * Baixa arquivo do storage (usado pelos workers)
 * 
 * @param {string} fileName - Nome do arquivo (claim check)
 * @returns {Promise<Buffer>} Dados descomprimidos
 */
export async function downloadFromStorage(fileName) {
  try {
    if (config.storage.type === 'minio' || !config.storage.type) {
      // MinIO/S3
      const dataStream = await minioClient.getObject(config.storage.bucket, fileName);
      
      // Ler stream e descomprimir
      const chunks = [];
      for await (const chunk of dataStream) {
        chunks.push(chunk);
      }
      
      const compressed = Buffer.concat(chunks);
      
      // Descomprimir GZIP
      const decompressed = gunzipSync(compressed);
      
      return decompressed;
      
    } else if (config.storage.type === 'local') {
      // Storage local
      const fs = await import('fs/promises');
      const { createGunzip } = await import('zlib');
      const { createReadStream } = await import('fs');
      const path = await import('path');
      
      const storagePath = config.storage.localPath || '/app/storage';
      const fullPath = path.join(storagePath, fileName);
      
      // Ler e descomprimir
      const chunks = [];
      const stream = createReadStream(fullPath).pipe(createGunzip());
      
      for await (const chunk of stream) {
        chunks.push(chunk);
      }
      
      return Buffer.concat(chunks);
    }
    
    throw new Error('Tipo de storage não suportado');
    
  } catch (error) {
    logger.error('Erro ao baixar arquivo do storage', {
      fileName,
      error: error.message,
    });
    throw error;
  }
}

/**
 * Remove arquivo do storage (após processamento)
 * 
 * @param {string} fileName - Nome do arquivo
 */
export async function deleteFromStorage(fileName) {
  try {
    if (config.storage.type === 'minio' || !config.storage.type) {
      await minioClient.removeObject(config.storage.bucket, fileName);
    } else if (config.storage.type === 'local') {
      const fs = await import('fs/promises');
      const path = await import('path');
      const storagePath = config.storage.localPath || '/app/storage';
      const fullPath = path.join(storagePath, fileName);
      await fs.unlink(fullPath);
    }
    
    logger.debug('Arquivo removido do storage', { fileName });
  } catch (error) {
    logger.warn('Erro ao remover arquivo do storage', {
      fileName,
      error: error.message,
    });
    // Não falhar se não conseguir remover
  }
}
