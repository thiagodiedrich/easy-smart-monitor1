"""
Modelo de Usuário.

Gerencia autenticação e autorização de usuários da API.
Suporta dois tipos de usuários: Frontend e Device (IoT).
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import ARRAY
import enum

from app.core.database import Base


class UserStatus(str, enum.Enum):
    """Status do usuário."""
    ACTIVE = "active"      # Ativo - pode fazer login
    INACTIVE = "inactive"  # Inativo - não pode fazer login
    BLOCKED = "blocked"    # Bloqueado - não pode fazer login (banido)


class UserType(str, enum.Enum):
    """Tipo de usuário."""
    FRONTEND = "frontend"  # Usuário para dashboard/frontend
    DEVICE = "device"      # Usuário para dispositivos IoT


class UserRole(str, enum.Enum):
    """Nível de acesso do usuário."""
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class User(Base):
    """Modelo de usuário para autenticação."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=True)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    organization_id = Column(ARRAY(Integer), nullable=False, index=True, default=[0])
    workspace_id = Column(ARRAY(Integer), nullable=False, index=True, default=[0])
    
    # Tipo de usuário (frontend ou device)
    user_type = Column(
        Enum(UserType),
        default=UserType.FRONTEND,
        nullable=False,
        index=True
    )
    
    # Status do usuário
    status = Column(
        Enum(UserStatus),
        default=UserStatus.ACTIVE,
        nullable=False,
        index=True
    )
    
    # Nível de acesso (RBAC)
    role = Column(
        JSONB,
        default={"role": UserRole.VIEWER.value},
        nullable=False
    )

    # Super admin global (apenas 1 no sistema)
    is_superadmin = Column(Boolean, default=False, nullable=False)
    
    # Metadados
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv6 suporta até 45 chars
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    refresh_token_hash = Column(String(255), nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<User(username='{self.username}', type='{self.user_type}', status='{self.status}')>"
    
    @property
    def can_login(self) -> bool:
        """Verifica se o usuário pode fazer login."""
        if self.status == UserStatus.BLOCKED:
            return False
        if self.status == UserStatus.INACTIVE:
            return False
        if self.locked_until and self.locked_until > datetime.utcnow():
            return False
        return True
    
    @classmethod
    async def get_by_username(cls, db: AsyncSession, username: str) -> Optional["User"]:
        """Busca usuário por username."""
        result = await db.execute(select(cls).where(cls.username == username))
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_by_username_and_type(
        cls,
        db: AsyncSession,
        username: str,
        user_type: UserType
    ) -> Optional["User"]:
        """Busca usuário por username e tipo."""
        result = await db.execute(
            select(cls).where(
                cls.username == username,
                cls.user_type == user_type
            )
        )
        return result.scalar_one_or_none()
    
    async def record_login(self, db: AsyncSession, ip_address: str) -> None:
        """Registra login bem-sucedido."""
        self.last_login_at = datetime.utcnow()
        self.last_login_ip = ip_address
        self.failed_login_attempts = 0
        self.locked_until = None
        await db.commit()
    
    async def record_failed_login(self, db: AsyncSession) -> None:
        """Registra tentativa de login falhada."""
        self.failed_login_attempts += 1
        
        # Bloquear após 5 tentativas falhadas por 30 minutos
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        await db.commit()
