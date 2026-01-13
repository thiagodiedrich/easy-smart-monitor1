"""Constantes para a integração Easy Smart Monitor."""
from typing import Final

# IMPORTANTE: O DOMAIN deve ser o nome exato da pasta em custom_components
DOMAIN: Final = "easy_smart_monitor1"

# Modo de Teste: Mude para False para habilitar comunicação real com a API
TEST_MODE: Final = True

# Configurações de Armazenamento Persistente (Módulo Store)
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}_storage"

# Chaves de Configuração utilizadas no Config Flow
CONF_API_HOST: Final = "api_host"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_EQUIPMENTS: Final = "equipments"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Intervalos de Tempo Padrão (em segundos)
DEFAULT_SCAN_INTERVAL: Final = 30  # Frequência de leitura local
DEFAULT_API_INTERVAL: Final = 60   # Frequência de envio para a API

# Definições de Tipos de Sensores Suportados
SENSOR_TYPES: Final = [
    "temperatura",
    "porta",
    "energia",
    "sirene",
    "botao",
    "humidade",
    "tensao",
    "corrente"
]

# Atributos para estruturação do JSON enviado à API
ATTR_EQUIPMENT_ID: Final = "equip_id"
ATTR_EQUIPMENT_UUID: Final = "equip_uuid"
ATTR_SENSOR_ID: Final = "sensor_id"
ATTR_SENSOR_UUID: Final = "sensor_uuid"
ATTR_SENSOR_TYPE: Final = "tipo"
ATTR_STATUS: Final = "status"
ATTR_TIMESTAMP: Final = "timestamp"

# Configurações da Sirene
SIREN_DELAY: Final = 120  # Tempo de porta aberta até disparar (segundos)