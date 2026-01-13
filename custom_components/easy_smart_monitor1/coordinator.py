import logging
from datetime import timedelta, datetime
import async_timeout

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

class EasySmartCoordinator(DataUpdateCoordinator):
    """
    Coordenador central da Easy Smart Monitor v1.0.10.
    Gere o ciclo de vida dos dados e monitoriza a integridade da fila e da API.
    """

    def __init__(self, hass: HomeAssistant, client, update_interval: int):
        """
        Inicializa o coordenador.

        :param hass: Instância do Home Assistant
        :param client: Instância do EasySmartClient (client.py)
        :param update_interval: Segundos entre sincronizações
        """
        self.client = client
        self.hass = hass

        # Variáveis de Estado para Sensores de Diagnóstico
        self.last_sync_success = True
        self.last_sync_time = "Pendente"
        self.consecutive_failures = 0
        self.last_error_message = None

        # Define o intervalo de atualização (mínimo de 10 segundos por segurança)
        seconds = max(update_interval if update_interval else DEFAULT_UPDATE_INTERVAL, 10)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=seconds),
        )

    async def _async_update_data(self):
        """
        Ciclo de atualização principal.
        Executa a sincronização da fila e atualiza as métricas de diagnóstico.
        """
        _LOGGER.debug("Iniciando ciclo de processamento da fila via Coordenador.")

        try:
            # Proteção global de 30 segundos para evitar travamento do event loop
            async with async_timeout.timeout(30):
                # O client.py agora retorna True se a fila foi enviada com sucesso
                success = await self.client.sync_queue()

                if success:
                    # Reset de métricas em caso de sucesso
                    self.last_sync_success = True
                    self.last_sync_time = datetime.now().strftime("%d/%m %H:%M:%S")
                    self.consecutive_failures = 0
                    self.last_error_message = None
                    _LOGGER.info("Sincronização bulk concluída com sucesso às %s.", self.last_sync_time)
                else:
                    # Incremento de falhas
                    self.last_sync_success = False
                    self.consecutive_failures += 1
                    self.last_error_message = "Falha de comunicação (verifique o servidor API)"
                    _LOGGER.warning(
                        "Falha na sincronização bulk. Tentativa consecutiva nº %s.",
                        self.consecutive_failures
                    )

                # Coleta dados adicionais do cliente para os sensores
                client_diag = self.client.get_diagnostics()

                # O retorno aqui alimenta o self.data do coordenador
                return {
                    "api_connected": self.last_sync_success,
                    "last_sync": self.last_sync_time,
                    "queue_size": client_diag.get("queue_size", 0),
                    "failures": self.consecutive_failures,
                    "host": client_diag.get("host")
                }

        except UpdateFailed as err:
            self.last_sync_success = False
            self.consecutive_failures += 1
            _LOGGER.error("UpdateFailed no coordenador: %s", err)
            raise err

        except Exception as err:
            # Captura erros inesperados sem tornar as entidades 'Unavailable'
            self.last_sync_success = False
            self.consecutive_failures += 1
            self.last_error_message = str(err)

            _LOGGER.error("Erro inesperado no Coordenador: %s", err)

            # Retorna o último estado conhecido para manter a interface funcional
            return {
                "api_connected": False,
                "last_sync": self.last_sync_time,
                "queue_size": len(self.client.queue),
                "error": str(err)
            }

    @callback
    def async_add_telemetry(self, data: dict):
        """
        Método thread-safe para os sensores injetarem dados na fila.
        """
        self.client.add_to_queue(data)

    async def force_sync(self):
        """
        Dispara uma sincronização imediata fora do intervalo programado.
        """
        _LOGGER.info("Sincronização manual solicitada via force_sync.")
        await self.async_refresh()