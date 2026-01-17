/**
 * Kafka Producer
 * 
 * Envia mensagens para o tópico de telemetria no Kafka.
 */
import { Kafka } from 'kafkajs';
import config from '../config.js';
import { logger } from '../utils/logger.js';

// Criar cliente Kafka
const kafka = new Kafka({
  clientId: config.kafka.clientId,
  brokers: config.kafka.brokers,
  retry: {
    retries: 5,
    initialRetryTime: 100,
    multiplier: 2,
    maxRetryTime: 30000,
  },
  requestTimeout: 30000,
  connectionTimeout: 3000,
});

// Criar producer
export const kafkaProducer = kafka.producer({
  maxInFlightRequests: 1,
  idempotent: true,
  transactionTimeout: 30000,
  allowAutoTopicCreation: true,
});

// Conectar producer
let isConnected = false;

export async function connectProducer() {
  if (isConnected) {
    return;
  }
  
  try {
    await kafkaProducer.connect();
    isConnected = true;
    logger.info('Kafka producer conectado', { 
      brokers: config.kafka.brokers,
      topic: config.kafka.topic,
    });
  } catch (error) {
    logger.error('Erro ao conectar Kafka producer', { 
      error: error.message,
      brokers: config.kafka.brokers,
    });
    throw error;
  }
}

// Conectar na inicialização
await connectProducer();

/**
 * Envia Claim Check (referência) para Kafka
 * 
 * CLAIM CHECK PATTERN: Envia apenas referência ao arquivo, não o payload completo.
 * 
 * @param {Object} claimCheck - Claim Check com referência ao arquivo no storage
 * @param {Object} metadata - Metadados (user_id, request_id, etc.)
 * @returns {Promise<void>}
 */
export async function sendTelemetryToKafka(claimCheck, metadata = {}) {
  if (!isConnected) {
    await connectProducer();
  }
  
  try {
    // Criar mensagem com Claim Check (apenas referência ~1KB)
    const message = {
      topic: config.kafka.topic,
      messages: [
        {
          key: metadata.userId?.toString() || metadata.username || 'unknown',
          value: JSON.stringify({
            claim_check: claimCheck.claim_check,
            storage_type: claimCheck.storage_type,
            storage_endpoint: claimCheck.storage_endpoint,
            bucket: claimCheck.bucket,
            file_size: claimCheck.file_size,
            original_size: claimCheck.original_size,
            compression: claimCheck.compression,
            timestamp: claimCheck.timestamp,
            metadata: {
              userId: metadata.userId,
              username: metadata.username,
              requestId: metadata.requestId,
              itemsCount: metadata.itemsCount || 0,
            },
          }),
          headers: {
            'content-type': 'application/json',
            'message-type': 'claim-check',
            'user-id': (metadata.userId || metadata.username || '').toString(),
            'request-id': metadata.requestId || '',
            'items-count': (metadata.itemsCount || 0).toString(),
            'file-size': (claimCheck.file_size || 0).toString(),
          },
        },
      ],
    };
    
    await kafkaProducer.send(message);
    
    logger.debug('Claim Check enviado para Kafka', {
      topic: config.kafka.topic,
      userId: metadata.userId || metadata.username,
      claimCheck: claimCheck.claim_check,
      fileSize: claimCheck.file_size,
      messageSize: JSON.stringify(message.messages[0].value).length,
    });
  } catch (error) {
    logger.error('Erro ao enviar Claim Check para Kafka', { 
      error: error.message, 
      stack: error.stack,
      topic: config.kafka.topic,
    });
    throw error;
  }
}

// Graceful disconnect
export async function disconnectProducer() {
  if (isConnected) {
    try {
      await kafkaProducer.disconnect();
      isConnected = false;
      logger.info('Kafka producer desconectado');
    } catch (error) {
      logger.error('Erro ao desconectar Kafka producer', { error: error.message });
    }
  }
}

// Adicionar método disconnect ao objeto exportado
kafkaProducer.disconnect = disconnectProducer;
