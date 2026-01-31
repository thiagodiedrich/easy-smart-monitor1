"""
Modelo de Dados de Telemetria.

Armazena dados de telemetria coletados dos sensores.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class TelemetryData(Base):
    """Modelo de dados de telemetria."""
    
    __tablename__ = "telemetry_data"
    
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False, index=True)
    
    value = Column(Float, nullable=True)
    status = Column(String(50), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Nome da coluna no DB: 'metadata'; atributo Python: extra_metadata (metadata é reservado no SQLAlchemy)
    extra_metadata = Column("metadata", JSONB, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    sensor = relationship("Sensor", back_populates="telemetry_data")
    
    __table_args__ = (
        Index("idx_equipment_timestamp", "equipment_id", "timestamp"),
        Index("idx_sensor_timestamp", "sensor_id", "timestamp"),
        Index("idx_timestamp", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<TelemetryData(sensor_id={self.sensor_id}, value={self.value}, timestamp={self.timestamp})>"
    
    @classmethod
    async def bulk_insert(
        cls,
        db: AsyncSession,
        data_list: List[dict],
    ) -> int:
        """Insere múltiplos registros de telemetria em bulk."""
        if not data_list:
            return 0
        
        telemetry_objects = [cls(**data) for data in data_list]
        db.add_all(telemetry_objects)
        # Não faz commit aqui, será feito pelo processador
        
        return len(telemetry_objects)
