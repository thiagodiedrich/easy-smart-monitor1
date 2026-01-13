"""Constantes para a integração Easy Smart Monitor."""
from homeassistant.const import (
    Platform,
    UnitOfTemperature,
    UnitOfPower,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    PERCENTAGE,
)

# Identificação da Integração
DOMAIN = "easy_smart_monitor1"
NAME = "Easy Smart Monitor"
VERSION = "1.0.11"

# Modo de Operação
# Se True: Simula sucesso na API (útil para testes de interface)
# Se False: Tenta comunicação real com o servidor
TEST_MODE = False

# Chaves de Configuração (Salvas no entry.data e entry.options)
CONF_API_HOST = "api_host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_EQUIPMENTS = "equipments"
CONF_UPDATE_INTERVAL = "update_interval"

# Configurações de Rede e Sincronização (Fila)
DEFAULT_UPDATE_INTERVAL = 60  # Segundos entre envios da fila para a API
MAX_RETRIES = 5               # Máximo de tentativas de reenvio em caso de erro
RETRY_DELAY = 10              # Segundos de espera entre tentativas de rede
STORAGE_FILE = "easy_smart_monitor1_queue.json"

# Plataformas Suportadas (v1.0.11)
# Carregamos primeiro os controles para que os sensores já iniciem respeitando-os
PLATFORMS: list[Platform] = [
    Platform.SWITCH,         # Equipamento Ativo, Sirene Ativa
    Platform.NUMBER,         # Intervalo de Coleta, Tempo de Porta
    Platform.SENSOR,         # Temperatura, Energia, Diagnósticos
    Platform.BINARY_SENSOR,  # Porta e Alerta de Sirene
]

# Valores Padrão de Hardware e Lógica (v1.0.11)
DEFAULT_INTERVALO_COLETA = 10    # Segundos (Mínimo recomendado para sensores)
DEFAULT_TEMPO_PORTA_ABERTA = 120 # Segundos (Tempo antes de disparar sirene)
DEFAULT_EQUIPAMENTO_ATIVO = True
DEFAULT_SIRENE_ATIVA = True

# Definições de Unidades de Medida
UNITS = {
    "temperatura": UnitOfTemperature.CELSIUS,
    "energia": UnitOfPower.WATT,
    "tensao": UnitOfElectricPotential.VOLT,
    "corrente": UnitOfElectricCurrent.AMPERE,
    "humidade": PERCENTAGE,
}

# Cabeçalhos de Comunicação API
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": f"EasySmartMonitor/{VERSION} (HomeAssistant)"
}

# Categorias de Sensores para Processamento Interno
SENSOR_TYPES = [
    "temperatura",
    "energia",
    "tensao",
    "corrente",
    "humidade",
    "status",
    "porta",
    "sirene"
]

# Mensagens de Diagnóstico
DIAG_CONEXAO_OK = "Conectado"
DIAG_CONEXAO_ERR = "Erro de Rede"
DIAG_PENDENTE = "Pendente"