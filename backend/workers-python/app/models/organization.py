"""
Modelo Organization.

Divisão interna do tenant (empresa, filial, unidade).
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class Organization(Base):
    """Modelo de organização."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    class Status(str, enum.Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"
        BLOCKED = "blocked"

    status = Column(
        Enum(Status, name="organization_status"),
        default=Status.ACTIVE,
        nullable=False
    )
    document = Column(String(50), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="organizations")
    workspaces = relationship("Workspace", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Organization(name='{self.name}', tenant_id='{self.tenant_id}')>"
