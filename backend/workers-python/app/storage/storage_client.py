"""
Storage Client - Claim Check Pattern

Gerencia download de arquivos do Object Storage (MinIO/S3).
"""
import gzip
import json
from typing import Dict, Any, Optional
from pathlib import Path
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class StorageClient:
    """Cliente para Object Storage (MinIO/S3)."""
    
    def __init__(self):
        """Inicializa cliente de storage."""
        self.client = None
        self.storage_type = settings.STORAGE_TYPE or 'minio'
        self._init_client()
    
    def _init_client(self):
        """Inicializa cliente baseado no tipo de storage."""
        if self.storage_type == 'minio':
            try:
                from minio import Minio
                
                # Parse endpoint (pode incluir porta)
                endpoint = settings.MINIO_ENDPOINT
                port = None
                if ':' in endpoint:
                    parts = endpoint.split(':')
                    endpoint = parts[0]
                    port = int(parts[1]) if len(parts) > 1 else None
                
                self.client = Minio(
                    endpoint,
                    port=port or int(settings.MINIO_PORT or '9000'),
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=settings.MINIO_USE_SSL == 'true',
                )
                
                logger.info(
                    "Cliente MinIO inicializado",
                    endpoint=endpoint,
                    port=port or settings.MINIO_PORT,
                    bucket=settings.MINIO_BUCKET,
                )
            except ImportError:
                logger.error("Biblioteca minio não instalada")
                raise
        
        elif self.storage_type == 'local':
            logger.info(
                "Storage local configurado",
                path=settings.STORAGE_LOCAL_PATH,
            )
        
        else:
            raise ValueError(f"Tipo de storage não suportado: {self.storage_type}")
    
    async def download_file(self, file_path: str) -> list:
        """
        Baixa arquivo do storage e descomprime.
        
        Args:
            file_path: Caminho do arquivo (claim check)
            
        Returns:
            Dados descomprimidos (dict ou list)
        """
        try:
            if self.storage_type == 'minio':
                # Baixar do MinIO
                from minio.error import S3Error
                
                try:
                    response = self.client.get_object(
                        settings.MINIO_BUCKET,
                        file_path,
                    )
                    
                    # Ler dados comprimidos
                    compressed_data = response.read()
                    response.close()
                    response.release_conn()
                    
                except S3Error as e:
                    logger.error(
                        "Erro ao baixar arquivo do MinIO",
                        file_path=file_path,
                        error=str(e),
                    )
                    raise
            
            elif self.storage_type == 'local':
                # Baixar do filesystem local
                storage_path = Path(settings.STORAGE_LOCAL_PATH or '/app/storage')
                full_path = storage_path / file_path
                
                if not full_path.exists():
                    raise FileNotFoundError(f"Arquivo não encontrado: {full_path}")
                
                with open(full_path, 'rb') as f:
                    compressed_data = f.read()
            
            else:
                raise ValueError(f"Tipo de storage não suportado: {self.storage_type}")
            
            # Descomprimir GZIP
            decompressed_data = gzip.decompress(compressed_data)
            
            # Deserializar JSON
            # Usar orjson se disponível (mais rápido)
            try:
                import orjson
                data = orjson.loads(decompressed_data)
            except ImportError:
                data = json.loads(decompressed_data.decode('utf-8'))
            
            logger.info(
                "Arquivo baixado e descomprimido",
                file_path=file_path,
                compressed_size=len(compressed_data),
                decompressed_size=len(decompressed_data),
            )
            
            # Garantir que retorna lista (formato esperado)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Se for dict com 'data', extrair
                if 'data' in data:
                    return data['data'] if isinstance(data['data'], list) else [data['data']]
                else:
                    return [data]
            else:
                return [data]
        
        except Exception as e:
            logger.error(
                "Erro ao baixar arquivo do storage",
                file_path=file_path,
                error=str(e),
                exc_info=True,
            )
            raise
    
    async def delete_file(self, file_path: str) -> None:
        """
        Remove arquivo do storage após processamento.
        
        Args:
            file_path: Caminho do arquivo
        """
        try:
            if self.storage_type == 'minio':
                self.client.remove_object(
                    settings.MINIO_BUCKET,
                    file_path,
                )
            
            elif self.storage_type == 'local':
                storage_path = Path(settings.STORAGE_LOCAL_PATH or '/app/storage')
                full_path = storage_path / file_path
                
                if full_path.exists():
                    full_path.unlink()
            
            logger.debug("Arquivo removido do storage", file_path=file_path)
        
        except Exception as e:
            logger.warn(
                "Erro ao remover arquivo do storage",
                file_path=file_path,
                error=str(e),
            )
            # Não falhar se não conseguir remover


# Instância global
storage_client = StorageClient()
