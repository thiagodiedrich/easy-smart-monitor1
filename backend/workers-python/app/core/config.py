"""
Configurações dos workers Python.
"""
import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Configurações dos workers."""
    
    # Aplicação
    APP_NAME: str = Field(default="Easy Smart Monitor Workers", description="Nome da aplicação")
    APP_VERSION: str = Field(default="1.0.0", description="Versão da aplicação")
    DEBUG: bool = Field(default=False, description="Modo debug")
    
    # Banco de Dados
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://easysmart:password@localhost:5432/easysmart_db",
        description="URL de conexão com PostgreSQL"
    )
    DATABASE_POOL_SIZE: int = Field(default=20, description="Tamanho do pool de conexões")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, description="Overflow máximo do pool")
    
    # Kafka
    KAFKA_BROKERS: str = Field(
        default="localhost:9092",
        description="Brokers Kafka (separados por vírgula)"
    )
    KAFKA_TOPIC: str = Field(default="telemetry.raw", description="Tópico Kafka para consumir")
    KAFKA_GROUP_ID: str = Field(default="telemetry-workers", description="Group ID do consumidor")
    KAFKA_BATCH_SIZE: int = Field(default=100, description="Tamanho do batch para processamento")
    KAFKA_AUTO_COMMIT: bool = Field(default=False, description="Auto commit de offsets")
    
    # Processamento
    BULK_INSERT_BATCH_SIZE: int = Field(default=1000, description="Tamanho do batch para inserts")
    MAX_RETRIES: int = Field(default=3, description="Número máximo de tentativas")
    RETRY_DELAY: int = Field(default=5, description="Delay entre tentativas (segundos)")
    
    # Storage (MinIO/S3)
    STORAGE_TYPE: str = Field(default="minio", description="Tipo de storage (minio, local, s3)")
    MINIO_ENDPOINT: str = Field(default="localhost", description="Endpoint do MinIO")
    MINIO_PORT: str = Field(default="9000", description="Porta do MinIO")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", description="Access key do MinIO")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", description="Secret key do MinIO")
    MINIO_BUCKET: str = Field(default="telemetry-raw", description="Bucket do MinIO")
    MINIO_USE_SSL: str = Field(default="false", description="Usar SSL no MinIO")
    STORAGE_LOCAL_PATH: str = Field(default="/app/storage", description="Caminho para storage local")
    
    # Limpeza de arquivos
    DELETE_FILE_AFTER_PROCESSING: bool = Field(default=True, description="Deletar arquivo após processar")
    FILE_RETENTION_DAYS: int = Field(default=7, description="Dias para manter arquivos não processados")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Nível de log")
    LOG_FORMAT: str = Field(default="json", description="Formato de log")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Instância global de configurações
settings = Settings()
