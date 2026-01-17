"""
Modelo de Sensor.

Representa um sensor individual dentro de um equipamento.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import Base


class Sensor(Base):
    """Modelo de sensor."""
    
    __tablename__ = "sensors"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)
    unit = Column(String(20), nullable=True)
    status = Column(String(20), default="ATIVO", nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False)
    
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    firmware = Column(String(50), nullable=True)
    hardware_id = Column(String(100), nullable=True)
    via_hub = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    equipment = relationship("Equipment", back_populates="sensors")
    telemetry_data = relationship("TelemetryData", back_populates="sensor", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Sensor(uuid='{self.uuid}', name='{self.name}', type='{self.type}')>"
    
    @classmethod
    async def get_by_uuid(cls, db: AsyncSession, uuid: str) -> Optional["Sensor"]:
        """Busca sensor por UUID."""
        result = await db.execute(select(cls).where(cls.uuid == uuid))
        return result.scalar_one_or_none()
