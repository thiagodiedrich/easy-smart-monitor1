import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    ATTR_LAST_SYNC,
    ATTR_QUEUE_SIZE,
    DIAG_CONEXAO_OK,
    DIAG_INTERNET_ERR,
    DIAG_SERVER_ERR,
    DIAG_TIMEOUT_RETRY,
    DIAG_PENDENTE,
    TEST_MODE,
    NAME
)

_LOGGER = logging.getLogger(__name__)

class EasySmartCoordinator(DataUpdateCoordinator):
    """
    Coordenador principal da integração {NAME}.
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
        self._last_status = DIAG_CONEXAO_OK
        self._last_sync_success: bool = True
        self._is_syncing = False # Trava para evitar sobreposição de ciclos

        # Validação de intervalo mínimo para proteger o sistema (60s)
        if update_interval is None:
            safe_interval = 60
        else:
            try:
                safe_interval = max(int(update_interval), 60)
            except (ValueError, TypeError):
                safe_interval = 60

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=None, # Desativamos o poll padrão para usar apenas nosso timer robusto
        )

        # Timer dedicado para garantir o envio para a API
        self._unsub_sync_timer = async_track_time_interval(
            self.hass,
            self._timer_sync_queue,
            timedelta(seconds=safe_interval)
        )

        _LOGGER.info(
            "Coordenador API Cloud [%s] inicializado com timer robusto. Ciclo de envio: %s segundos.",
            DOMAIN,
            safe_interval
        )

    async def _timer_sync_queue(self, now=None):
        """Dispara o ciclo de sincronização via timer externo."""
        if self._is_syncing:
            _LOGGER.debug("Sincronização já em andamento, pulando este ciclo do timer.")
            return
        await self.async_refresh()

    async def _async_update_data(self) -> Dict[str, Any]:
        """
        Método chamado automaticamente pelo HA a cada intervalo de tempo.
        Tenta esvaziar a fila enviando dados para a API.
        """
        if self._is_syncing:
            return self._get_diagnostics_payload()
        
        self._is_syncing = True
        _LOGGER.info("Iniciando ciclo de sincronização (Fila: %s itens)", len(self.client.queue))

        # 1. Muda status para Timeout/Retry no início do ciclo
        self._last_status = DIAG_TIMEOUT_RETRY
        self.async_set_updated_data(self._get_diagnostics_payload())

        try:
            # Chama o método de sincronia do cliente
            success = await self.client.sync_queue()

            # Atualiza os estados internos baseado no resultado
            if success:
                self._last_status = DIAG_CONEXAO_OK
                self._last_sync_success = True
                _LOGGER.info("Sincronização finalizada com SUCESSO.")
            else:
                self._last_sync_success = False
                # 2. Se falhar, verifica se o problema é a Internet ou o Servidor
                if await self.client.check_internet():
                    self._last_status = DIAG_SERVER_ERR
                    _LOGGER.warning("Ciclo finalizado com erro: FALHA DE SERVIDOR (Internet OK).")
                else:
                    self._last_status = DIAG_INTERNET_ERR
                    _LOGGER.warning("Ciclo finalizado com erro: FALHA DE INTERNET.")

            return self._get_diagnostics_payload()

        except ConfigEntryAuthFailed as e:
            self._last_sync_success = False
            self._last_status = DIAG_SERVER_ERR
            raise e
        except Exception as err:
            self._last_sync_success = False
            if await self.client.check_internet():
                self._last_status = DIAG_SERVER_ERR
            else:
                self._last_status = DIAG_INTERNET_ERR
            _LOGGER.error("Erro crítico no ciclo de sincronização: %s", err)
            return self._get_diagnostics_payload()
        finally:
            self._is_syncing = False
            # Força uma atualização final para garantir que o status de erro apareça
            self.async_set_updated_data(self._get_diagnostics_payload())

    def _get_diagnostics_payload(self) -> Dict[str, Any]:
        """Compila os dados de saúde do sistema para os sensores de diagnóstico."""
        client_stats = self.client.get_diagnostics()

        return {
            "status_conexao": self._last_status,
            ATTR_LAST_SYNC: client_stats.get("last_communication", "Aguardando..."),
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
        return self._last_status == DIAG_CONEXAO_OK

    @property
    def last_sync_time(self) -> str:
        """Retorna a string formatada da última sincronização."""
        return self.client.get_diagnostics().get("last_communication", "Aguardando...")

    @property
    def is_connected(self) -> bool:
        """Atalho para verificar conexão."""
        return self._last_sync_success

    @property
    def queue_size(self) -> int:
        """Retorna o tamanho atual da fila."""
        return len(self.client.queue)

    @property
    def update_interval_seconds(self) -> float:
        """Retorna o intervalo atual em segundos."""
        return self.update_interval.total_seconds() if self.update_interval else 0

    @update_interval_seconds.setter
    def update_interval_seconds(self, value: int):
        """Atualiza o intervalo de atualização dinamicamente."""
        # Se o valor for menor que 60 segundos, assume 60 para não prejudicar 
        # o desempenho do Home Assistant e da API Cloud (Online).
        safe_interval = max(int(value), 60)
        self.update_interval = timedelta(seconds=safe_interval)
        
        # Atualiza também o timer robusto
        if hasattr(self, '_unsub_sync_timer') and self._unsub_sync_timer:
            self._unsub_sync_timer() # Cancela o anterior
            
        self._unsub_sync_timer = async_track_time_interval(
            self.hass,
            self._timer_sync_queue,
            self.update_interval
        )
        
        _LOGGER.info("Intervalo de atualização do Coordinator [%s] ajustado para %s segundos.", self.name, safe_interval)

    def shutdown(self):
        """Limpa recursos ao descarregar."""
        if hasattr(self, '_unsub_sync_timer') and self._unsub_sync_timer:
            self._unsub_sync_timer()
            self._unsub_sync_timer = None