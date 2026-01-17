"""
Consumidor Kafka para processar telemetria.

Consome mensagens do tópico 'telemetry.raw' e processa em lotes.
"""
import asyncio
import json
import logging
import signal
import sys
from typing import List, Dict, Any
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from app.processors.telemetry_processor import TelemetryProcessor
from app.storage.storage_client import storage_client
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

# Configurar logging
setup_logging()
logger = get_logger(__name__)


class TelemetryKafkaConsumer:
    """Consumidor Kafka para dados de telemetria."""
    
    def __init__(self):
        """Inicializa o consumidor Kafka."""
        self.consumer = None
        self.processor = TelemetryProcessor()
        self.running = False
        self._setup_consumer()
        logger.info(
            f"Consumidor Kafka inicializado. Tópico: {settings.KAFKA_TOPIC}, "
            f"Group: {settings.KAFKA_GROUP_ID}, Brokers: {settings.KAFKA_BROKERS}"
        )
    
    def _setup_consumer(self):
        """Configura o consumidor Kafka."""
        brokers = settings.KAFKA_BROKERS.split(',')
        
        self.consumer = KafkaConsumer(
            settings.KAFKA_TOPIC,
            bootstrap_servers=brokers,
            group_id=settings.KAFKA_GROUP_ID,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda m: m.decode('utf-8') if m else None,
            enable_auto_commit=settings.KAFKA_AUTO_COMMIT,
            auto_offset_reset='earliest',
            max_poll_records=settings.KAFKA_BATCH_SIZE,
            consumer_timeout_ms=5000,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
        )
    
    async def consume(self):
        """
        Loop principal de consumo.
        
        Processa mensagens em lotes para melhor performance.
        """
        self.running = True
        logger.info("Iniciando consumo de telemetria do Kafka...")
        
        try:
            while self.running:
                # Buscar lote de mensagens (síncrono, mas não bloqueia muito)
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    await asyncio.sleep(0.1)
                    continue
                
                # Processar lote
                await self._process_batch(message_batch)
                
        except KeyboardInterrupt:
            logger.info("Interrupção recebida. Encerrando consumidor...")
        except Exception as e:
            logger.error(f"Erro no consumidor Kafka: {e}", exc_info=True)
        finally:
            self._cleanup()
    
    async def _process_batch(self, message_batch: Dict):
        """
        Processa um lote de mensagens.
        
        Args:
            message_batch: Dicionário de partição -> lista de mensagens
        """
        all_messages = []
        partitions_to_commit = []
        
        # Coletar todas as mensagens do lote
        for topic_partition, messages in message_batch.items():
            for message in messages:
                all_messages.append({
                    'key': message.key,
                    'value': message.value,
                    'partition': topic_partition.partition,
                    'offset': message.offset,
                })
            partitions_to_commit.append(topic_partition)
        
        if not all_messages:
            return
        
        logger.info(f"Processando lote de {len(all_messages)} mensagens")
        
        try:
            # Processar cada mensagem (Claim Check Pattern)
            for msg in all_messages:
                user_id = msg['key'] or 'unknown'
                message_data = msg['value']
                
                try:
                    # Verificar se é Claim Check (novo formato) ou payload completo (compatibilidade)
                    is_claim_check = (
                        isinstance(message_data, dict) and 
                        'claim_check' in message_data
                    )
                    
                    if is_claim_check:
                        # CLAIM CHECK PATTERN: Baixar arquivo do storage
                        claim_check = message_data['claim_check']
                        storage_type = message_data.get('storage_type', 'minio')
                        
                        logger.info(
                            "Processando Claim Check",
                            claim_check=claim_check,
                            user_id=user_id,
                            file_size=message_data.get('file_size', 0),
                        )
                        
                        # Baixar arquivo do storage
                        telemetry_data = await storage_client.download_file(claim_check)
                        
                        # Garantir que é array
                        if not isinstance(telemetry_data, list):
                            telemetry_data = [telemetry_data]
                        
                    else:
                        # Formato antigo (compatibilidade): payload completo
                        logger.warn("Recebido payload completo (formato antigo). Migre para Claim Check Pattern.")
                        
                        if isinstance(message_data, dict) and 'data' in message_data:
                            telemetry_data = message_data['data']
                        else:
                            telemetry_data = [message_data] if not isinstance(message_data, list) else message_data
                    
                    # Processar telemetria
                    async with AsyncSessionLocal() as db:
                        result = await self.processor.process_bulk(
                            int(user_id) if user_id.isdigit() else 1,
                            telemetry_data,
                            db,
                        )
                        
                        logger.info(
                            "Telemetria processada",
                            user_id=user_id,
                            processed=result['processed'],
                            inserted=result.get('inserted', 0),
                            errors=len(result.get('errors', [])),
                        )
                        
                        # Deletar arquivo após processamento bem-sucedido (se Claim Check)
                        if is_claim_check and settings.DELETE_FILE_AFTER_PROCESSING:
                            try:
                                await storage_client.delete_file(claim_check)
                                logger.debug("Arquivo removido após processamento", claim_check=claim_check)
                            except Exception as e:
                                logger.warn("Erro ao remover arquivo", claim_check=claim_check, error=str(e))
                
                except Exception as e:
                    logger.error(
                        "Erro ao processar mensagem",
                        user_id=user_id,
                        error=str(e),
                        exc_info=True
                    )
                    # Em caso de erro, não commita (permite reprocessamento)
                    # Arquivo permanece no storage para reprocessamento
            
            # Commit do offset (sucesso)
            if not settings.KAFKA_AUTO_COMMIT:
                self.consumer.commit()
            logger.debug(f"Offset commitado para {len(partitions_to_commit)} partições")
            
        except Exception as e:
            logger.error(f"Erro ao processar lote: {e}", exc_info=True)
            # Em caso de erro, não commita (permite reprocessamento)
            # TODO: Implementar dead letter queue para mensagens com erro persistente
    
    def _cleanup(self):
        """Limpa recursos."""
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Consumidor Kafka encerrado")
            except Exception as e:
                logger.error(f"Erro ao fechar consumidor: {e}")
    
    def stop(self):
        """Para o consumidor graciosamente."""
        self.running = False
        logger.info("Solicitação de parada recebida")


async def main():
    """Função principal para executar o consumidor."""
    consumer = TelemetryKafkaConsumer()
    
    # Handler para graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Sinal {sig} recebido, encerrando...")
        consumer.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await consumer.consume()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
        sys.exit(0)
