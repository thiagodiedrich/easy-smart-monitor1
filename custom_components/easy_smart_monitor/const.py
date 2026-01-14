"""Constantes exaustivas para a integração Easy Smart Monitor."""
from homeassistant.const import (
    Platform,
    UnitOfTemperature,
    UnitOfPower,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    PERCENTAGE,
)

# Identificação da Integração
DOMAIN = "easy_smart_monitor"
NAME = "Easy Smart Monitor"
VERSION = "1.1.0"
MANUFACTURER = "Easy Smart"

# Modo de Operação
# Se True: Habilita preenchimento automático e pula validação de rede no config_flow
TEST_MODE = False

# Chaves de Configuração (Core)
CONF_API_HOST = "api_host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_EQUIPMENTS = "equipments"
CONF_UPDATE_INTERVAL = "update_interval"

# Chaves Internas de Equipamento e Sensores
CONF_EQUIP_UUID = "uuid"
CONF_EQUIP_NAME = "nome"
CONF_EQUIP_LOCAL = "local"
CONF_SENSORS = "sensors"
CONF_SENSOR_UUID = "uuid"
CONF_SENSOR_TYPE = "tipo"
CONF_HA_ENTITY = "ha_entity_id"

# Configurações de Fila e Rede
DEFAULT_UPDATE_INTERVAL = 120
MAX_RETRIES = 5
RETRY_DELAY = 10
STORAGE_FILE = "easy_smart_monitor_queue.json"

# Plataformas Suportadas (v1.0.11)
# A ordem garante que controles sejam criados antes dos sensores dependentes
PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

# Definições de Hardware e Lógica Industrial (v1.0.11)
CONF_ATIVO = "ativo"
CONF_SIRENE_ATIVA = "sirene_ativa"
CONF_INTERVALO_COLETA = "intervalo_coleta"
CONF_TEMPO_PORTA = "tempo_porta"

DEFAULT_INTERVALO_COLETA = 60
DEFAULT_TEMPO_PORTA_ABERTA = 120
DEFAULT_EQUIPAMENTO_ATIVO = True
DEFAULT_SIRENE_ATIVA = False

# Mapeamento de Unidades de Medida Oficiais HA
UNITS = {
    "temperatura": UnitOfTemperature.CELSIUS,
    "energia": UnitOfPower.WATT,
    "tensao": UnitOfElectricPotential.VOLT,
    "corrente": UnitOfElectricCurrent.AMPERE,
    "umidade": PERCENTAGE,
}

# Cabeçalhos de Comunicação API
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": f"EasySmartMonitor/{VERSION} (HomeAssistant; @thiagodiedrich)"
}

# Categorias e Tipos de Sensores
SENSOR_TYPES = [
    "temperatura",
    "energia",
    "tensao",
    "corrente",
    "umidade",
    "status",
    "porta",
    "sirene",
    "botao"
]

# Estados de Diagnóstico (Traduções de Status)
DIAG_CONEXAO_OK = "Conectado"
DIAG_CONEXAO_ERR = "Erro de Rede"
DIAG_PENDENTE = "Pendente"

# Categorias de Entidades
ATTR_LAST_SYNC = "last_sync"
ATTR_QUEUE_SIZE = "queue_size"