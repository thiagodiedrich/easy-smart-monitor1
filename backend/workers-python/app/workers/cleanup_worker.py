"""
Worker de limpeza de arquivos antigos do storage.

Remove arquivos processados após período de retenção.
"""
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import structlog

from app.core.config import settings
from app.storage.storage_client import storage_client

logger = structlog.get_logger(__name__)


async def cleanup_old_files():
    """
    Remove arquivos antigos do storage.
    
    Executa limpeza baseada em FILE_RETENTION_DAYS.
    """
    retention_days = settings.FILE_RETENTION_DAYS
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    logger.info(
        "Iniciando limpeza de arquivos antigos",
        cutoff_date=cutoff_date.isoformat(),
        retention_days=retention_days,
    )
    
    try:
        if storage_client.storage_type == 'minio':
            # Listar objetos no bucket
            objects = storage_client.client.list_objects(
                settings.MINIO_BUCKET,
                prefix='telemetry/',
                recursive=True,
            )
            
            deleted_count = 0
            for obj in objects:
                # Verificar data do objeto
                if obj.last_modified < cutoff_date:
                    try:
                        storage_client.client.remove_object(
                            settings.MINIO_BUCKET,
                            obj.object_name,
                        )
                        deleted_count += 1
                        logger.debug("Arquivo antigo removido", file=obj.object_name)
                    except Exception as e:
                        logger.warn("Erro ao remover arquivo", file=obj.object_name, error=str(e))
            
            logger.info("Limpeza concluída", deleted_count=deleted_count)
        
        elif storage_client.storage_type == 'local':
            # Limpeza de arquivos locais
            storage_path = Path(settings.STORAGE_LOCAL_PATH or '/app/storage')
            telemetry_path = storage_path / 'telemetry'
            
            if not telemetry_path.exists():
                return
            
            deleted_count = 0
            for file_path in telemetry_path.rglob('*.json.gz'):
                try:
                    file_stat = file_path.stat()
                    file_time = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    if file_time < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug("Arquivo antigo removido", file=str(file_path))
                except Exception as e:
                    logger.warn("Erro ao remover arquivo", file=str(file_path), error=str(e))
            
            logger.info("Limpeza concluída", deleted_count=deleted_count)
    
    except Exception as e:
        logger.error("Erro na limpeza de arquivos", exc_info=e)


async def run_cleanup_worker():
    """Loop principal do worker de limpeza."""
    logger.info("Worker de limpeza iniciado")
    
    while True:
        try:
            await cleanup_old_files()
            # Executar limpeza a cada 24 horas
            await asyncio.sleep(24 * 60 * 60)
        except Exception as e:
            logger.error("Erro no worker de limpeza", exc_info=e)
            await asyncio.sleep(3600)  # Esperar 1 hora antes de tentar novamente


if __name__ == '__main__':
    asyncio.run(run_cleanup_worker())
