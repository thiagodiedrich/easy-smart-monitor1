"""Constantes para a integração Easy Smart Monitor."""
from typing import Final

# Domínio da integração
DOMAIN: Final = "easy_smart_monitor"

# Configurações de Armazenamento (Store)
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}_storage"

# Chaves de Configuração (Config Flow)
CONF_API_HOST: Final = "api_host"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_EQUIPMENTS: Final = "equipments"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Valores Padrão
DEFAULT_SCAN_INTERVAL: Final = 30  # Verificação da fila local (segundos)
DEFAULT_API_INTERVAL: Final = 60   # Sincronização com a API REST (segundos)

# Definições de Sensores
# Estes tipos são usados para ícones automáticos e classes de dispositivo no HA
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

# Atributos de Log e API
ATTR_EQUIPMENT_ID: Final = "equip_id"
ATTR_SENSOR_TYPE: Final = "tipo"
ATTR_STATUS: Final = "status"
ATTR_TIMESTAMP: Final = "timestamp"

# Estados da Sirene
STATE_SIREN_ON: Final = "on"
STATE_SIREN_OFF: Final = "off"
SIREN_DELAY: Final = 120  # Tempo em segundos para disparo