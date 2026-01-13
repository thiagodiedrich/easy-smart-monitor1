import logging
import time
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class EasySmartCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Classe para gerenciar a atualização de dados e sincronização com a API."""

    def __init__(self, hass: HomeAssistant, client: Any, update_interval: int):
        """Inicializa o coordenador."""
        self.client = client
        self.hass = hass
        
        # O intervalo do Coordinator define a frequência de verificação da fila
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

        # Controle de tempo para envio à API (independente do poll de sensores)
        self.last_api_sync = time.time()
        self.api_sync_interval = 60  # Valor padrão em segundos

    async def _async_update_data(self) -> Dict[str, Any]:
        """
        Atualiza os dados internamente. 
        Este método é chamado automaticamente pelo Home Assistant 
        com base no update_interval.
        """
        try:
            current_time = time.time()

            # Lógica de Sincronização com a API REST
            # Só tenta enviar se o intervalo (60s) passou E se há itens na fila
            if (current_time - self.last_api_sync) >= self.api_sync_interval:
                if len(self.client.queue) > 0:
                    _LOGGER.debug(
                        "Iniciando sincronização programada: %s itens na fila", 
                        len(self.client.queue)
                    )
                    
                    success = await self.client.send_queue()
                    
                    if success:
                        self.last_api_sync = current_time
                        _LOGGER.info("Sincronização com API concluída com sucesso.")
                    else:
                        _LOGGER.warning("Falha na sincronização. Dados mantidos para a próxima tentativa.")
                else:
                    _LOGGER.debug("Fila vazia. Sincronização ignorada.")
                    self.last_api_sync = current_time

            # Retorna o status atual para as entidades
            return {
                "queue_size": len(self.client.queue),
                "last_sync": self.last_api_sync,
                "api_connected": self.client.token is not None
            }

        except Exception as err:
            raise UpdateFailed(f"Erro ao comunicar com a lógica do monitor: {err}")

    @property
    def queue_count(self) -> int:
        """Retorna a quantidade de itens aguardando envio."""
        return len(self.client.queue)