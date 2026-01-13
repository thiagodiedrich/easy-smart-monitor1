import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Any, List, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    STORAGE_VERSION,
    STORAGE_KEY,
    ATTR_TIMESTAMP
)

_LOGGER = logging.getLogger(__name__)

class EasySmartClient:
    """Cliente API com gerenciamento de fila persistente e autenticação."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        hass: HomeAssistant
    ):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.session = session
        self.hass = hass
        self.token: Optional[str] = None
        self.queue: List[Dict[str, Any]] = []

        # Inicializa o armazenamento persistente do Home Assistant
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def load_queue_from_disk(self) -> None:
        """Carrega dados salvos anteriormente no disco (.storage)."""
        try:
            stored_data = await self._store.async_load()
            if stored_data and "queue" in stored_data:
                self.queue = stored_data["queue"]
                _LOGGER.info("Fila carregada do disco: %s itens pendentes", len(self.queue))
        except Exception as err:
            _LOGGER.error("Erro ao carregar fila do disco: %s", err)

    async def _save_queue_to_disk(self) -> None:
        """Salva o estado atual da fila no disco de forma atômica."""
        try:
            await self._store.async_save({"queue": self.queue})
        except Exception as err:
            _LOGGER.error("Erro ao salvar fila no disco: %s", err)

    def add_to_queue(self, data: Dict[str, Any]) -> None:
        """Adiciona um novo evento à fila e agenda persistência."""
        # Garante que o timestamp esteja presente
        if ATTR_TIMESTAMP not in data:
            data[ATTR_TIMESTAMP] = datetime.now().isoformat()

        self.queue.append(data)
        # Agenda o salvamento em disco sem bloquear a thread principal
        self.hass.async_create_task(self._save_queue_to_disk())

    async def authenticate(self) -> bool:
        """Realiza o login na API e armazena o Token JWT."""
        url = f"{self.host}/api/login"
        payload = {"username": self.username, "password": self.password}

        try:
            async with self.session.post(url, json=payload, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get("token")
                    _LOGGER.info("Autenticação bem-sucedida com a API Easy Smart")
                    return True

                _LOGGER.error("Falha na autenticação: Status %s", response.status)
                return False
        except Exception as err:
            _LOGGER.error("Erro ao conectar na API para login: %s", err)
            return False

    async def send_queue(self) -> bool:
        """Envia a fila acumulada para a API REST."""
        if not self.queue:
            return True

        if not self.token:
            if not await self.authenticate():
                return False

        url = f"{self.host}/api/sync"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            async with self.session.post(
                url,
                json=self.queue,
                headers=headers,
                timeout=15
            ) as response:
                if response.status == 200:
                    _LOGGER.info("Sincronização de %s itens concluída", len(self.queue))
                    self.queue.clear()