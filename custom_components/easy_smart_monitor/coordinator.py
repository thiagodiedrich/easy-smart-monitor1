import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    ATTR_LAST_SYNC,
    ATTR_QUEUE_SIZE,
    DIAG_CONEXAO_OK,
    DIAG_CONEXAO_ERR,
    DIAG_PENDENTE,
    TEST_MODE
)

_LOGGER = logging.getLogger(__name__)

class EasySmartCoordinator(DataUpdateCoordinator):
    """
    Coordenador principal da integração Easy Smart Monitor.
    Gerencia a sincronização de dados entre a fila local (Client) e o Home Assistant,
    além de fornecer o estado de saúde para os sensores de diagnóstico.
    """

    def __init__(self, hass: HomeAssistant, client, update_interval: int):
        """
        Inicializa o coordenador.

        :param hass: Instância do Home Assistant.
        :param client: Instância do EasySmartClient (configurada no __init__.py).
        :param update_interval: Tempo em segundos entre as tentativas de envio bulk.
        """
        self.client = client
        self.hass = hass

        # Estado interno de diagnóstico
        self._last_sync_success: bool = True
        self._last_sync_time: str = "Aguardando..."

        # Validação de intervalo mínimo para proteger o sistema (30s)
        # Se update_interval for None ou menor que 30, força o padrão.
        safe_interval = max(update_interval or DEFAULT_UPDATE_INTERVAL, 30)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=safe_interval),
        )

        _LOGGER.debug(
            "Coordinator inicializado. Intervalo de sincronia: %s segundos. Modo Teste: %s",
            safe_interval,
            TEST_MODE
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """
        Método chamado automaticamente pelo HA a cada intervalo de tempo.
        Tenta esvaziar a fila enviando dados para a API.
        """
        _LOGGER.debug("Iniciando ciclo de sincronização agendado (Fila atual: %s)", len(self.client.queue))

        try:
            # Chama o método de sincronia do cliente (que lida com retries e auth)
            success = await self.client.sync_queue()

            # Atualiza os estados internos baseado no resultado
            if success:
                self._last_sync_success = True
                self._last_sync_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                if len(self.client.queue) == 0:
                    _LOGGER.debug("Sincronização OK. Fila limpa.")
            else:
                self._last_sync_success = False
                _LOGGER.warning("Ciclo de sincronização falhou. Os dados permanecerão no disco para a próxima tentativa.")

            # Retorna o dicionário de dados que alimenta os sensores de diagnóstico
            return self._get_diagnostics_payload()

        except ConfigEntryAuthFailed as e:
            # Erro específico de autenticação deve ser repassado para o HA pedir reconfiguração
            self._last_sync_success = False
            raise e
        except Exception as err:
            self._last_sync_success = False
            _LOGGER.error("Erro crítico não tratado no Coordinator: %s", err)
            raise UpdateFailed(f"Erro de comunicação com API: {err}") from err

    def _get_diagnostics_payload(self) -> Dict[str, Any]:
        """Compila os dados de saúde do sistema para os sensores de diagnóstico."""
        client_stats = self.client.get_diagnostics()

        return {
            "status_conexao": DIAG_CONEXAO_OK if self._last_sync_success else DIAG_CONEXAO_ERR,
            ATTR_LAST_SYNC: self._last_sync_time,
            ATTR_QUEUE_SIZE: client_stats.get("queue_size", 0),
            "api_host": client_stats.get("api_host", "Desconhecido"),
            "authenticated": client_stats.get("is_authenticated", False),
            "storage_path": client_stats.get("storage_location", "")
        }

    async def async_add_telemetry(self, data: Dict[str, Any]):
        """
        Recebe dados dos sensores (temperatura, porta, etc) e enfileira.
        IMPORTANTE: Força uma atualização parcial da interface para mostrar
        o aumento da fila instantaneamente, sem esperar o intervalo de poll.
        """
        if not data:
            return

        # 1. Adiciona à fila e persiste no disco (via Client)
        self.client.add_to_queue(data)

        # 2. Notifica o HA que o tamanho da fila mudou (Update Push)
        # Isso faz o sensor de "Tamanho da Fila" atualizar na hora no Dashboard
        self.async_set_updated_data(self._get_diagnostics_payload())

        _LOGGER.debug(
            "Telemetria adicionada: %s. Novo tamanho da fila: %s",
            data.get('tipo'),
            len(self.client.queue)
        )

    # --- Propriedades Auxiliares para Acesso Rápido pelas Entidades ---

    @property
    def last_sync_success(self) -> bool:
        """Retorna True se a última conexão foi bem sucedida."""
        return self._last_sync_success

    @property
    def last_sync_time(self) -> str:
        """Retorna a string formatada da última sincronização."""
        return self._last_sync_time

    @property
    def is_connected(self) -> bool:
        """Atalho para verificar conexão."""
        return self._last_sync_success

    @property
    def queue_size(self) -> int:
        """Retorna o tamanho atual da fila."""
        return len(self.client.queue)