"""
Modelo de Equipamento.

Representa um dispositivo físico que possui sensores.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import Base


class Equipment(Base):
    """Modelo de equipamento/dispositivo."""
    
    __tablename__ = "equipments"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=True)
    status = Column(String(20), default="ATIVO", nullable=False)
    collection_interval = Column(Integer, default=60, nullable=False)
    siren_active = Column(Boolean, default=False, nullable=False)
    siren_time = Column(Integer, default=120, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    sensors = relationship("Sensor", back_populates="equipment", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Equipment(uuid='{self.uuid}', name='{self.name}', status='{self.status}')>"
    
    @classmethod
    async def get_by_uuid(cls, db: AsyncSession, uuid: str) -> Optional["Equipment"]:
        """Busca equipamento por UUID."""
        result = await db.execute(select(cls).where(cls.uuid == uuid))
        return result.scalar_one_or_none()
