"""Modelos SQLAlchemy para o banco de dados"""

from app.core.database import Base

# Importar todos os modelos para garantir registro
from app.models.user import User
from app.models.equipment import Equipment
from app.models.sensor import Sensor
from app.models.telemetry_data import TelemetryData

__all__ = ["Base", "User", "Equipment", "Sensor", "TelemetryData"]
