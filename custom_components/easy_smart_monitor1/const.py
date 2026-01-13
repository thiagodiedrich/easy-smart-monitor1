"""Constantes para a integração Easy Smart Monitor."""

# Identificação da Integração
DOMAIN = "easy_smart_monitor1"
VERSION = "1.0.10"

# Modo de Operação
# True: Simula sucesso na API (útil para testes de interface)
# False: Requer servidor de API ativo e funcional
TEST_MODE = True

# Chaves de Configuração (Salvas no entry.data)
CONF_API_HOST = "api_host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Configurações de Tempo e Sincronização
DEFAULT_UPDATE_INTERVAL = 60  # Segundos entre envios da fila
SIREN_DELAY = 60              # Segundos de porta aberta para soar o alarme
RETRY_DELAY = 5               # Segundos de espera após falha de rede
MAX_RETRIES = 3               # Máximo de tentativas de reenvio antes de desistir

# Tipos de Sensores Suportados
# Organizados por categoria para facilitar o processamento no sensor.py
SENSOR_TYPES = [
    # Telemetria (Numéricos)
    "temperatura",
    "energia",
    "tensao",
    "corrente",
    "humidade",

    # Status (Texto e Binário)
    "status",
    "porta",
    "sirene",

    # Diagnóstico de Sistema (Auto-gerados na v1.0.10)
    "diagnostico_conexao",
    "diagnostico_sincro"
]

# Persistência e Comunicação
STORAGE_FILE = "easy_smart_monitor1_queue.json"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": f"EasySmartMonitor/{VERSION} (HomeAssistant)"
}

# Definições de Unidades (Opcional, mas útil para centralizar)
UNITS = {
    "temperatura": "°C",
    "energia": "W",
    "tensao": "V",
    "corrente": "A",
    "humidade": "%"
}