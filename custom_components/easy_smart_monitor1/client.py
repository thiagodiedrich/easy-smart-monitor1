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
    ATTR_TIMESTAMP,
    TEST_MODE
)

_LOGGER = logging.getLogger(__name__)

class EasySmartClient:
    """Cliente API com gerenciamento de fila persistente e suporte a Modo de Teste."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        hass: HomeAssistant
    ):
        # Limpa a URL para evitar erros de barra dupla
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.session = session
        self.hass = hass
        self.token: Optional[str] = None
        self.queue: List[Dict[str, Any]] = []

        # Gerenciador de armazenamento persistente (JSON no disco)
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def load_queue_from_disk(self) -> None:
        """Carrega eventos pendentes salvos anteriormente no disco."""
        try:
            stored_data = await self._store.async_load()
            if stored_data and "queue" in stored_data:
                self.queue = stored_data["queue"]
                _LOGGER.info("Fila persistente carregada: %s itens pendentes", len(self.queue))
        except Exception as err:
            _LOGGER.error("Erro ao carregar fila do disco: %s", err)

    async def _save_queue_to_disk(self) -> None:
        """Salva a fila atual no disco (.storage) de forma segura."""
        try:
            await self._store.async_save({"queue": self.queue})
        except Exception as err:
            _LOGGER.error("Erro ao salvar fila no disco: %s", err)

    def add_to_queue(self, data: Dict[str, Any]) -> None:
        """Adiciona um novo registro à fila e sincroniza com o disco."""
        if ATTR_TIMESTAMP not in data:
            data[ATTR_TIMESTAMP] = datetime.now().isoformat()

        self.queue.append(data)
        # Salva no disco em background
        self.hass.async_create_task(self._save_queue_to_disk())
        _LOGGER.debug("Evento adicionado à fila: %s", data)

    async def authenticate(self) -> bool:
        """Realiza a autenticação JWT. No TEST_MODE, sempre retorna True."""
        if TEST_MODE:
            _LOGGER.info("[TEST MODE] Autenticação simulada com sucesso.")
            self.token = "fake_test_token"
            return True

        url = f"{self.host}/api/login"
        payload = {"username": self.username, "password": self.password}

        try:
            async with self.session.post(url, json=payload, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get("token")
                    return True

                _LOGGER.error("Falha na autenticação API: Status %s", response.status)
                return False
        except Exception as err:
            _LOGGER.error("Erro de conexão na autenticação: %s", err)
            return False

    async def send_queue(self) -> bool:
        """Despacha a fila para a API. No TEST_MODE, apenas limpa a fila."""
        if not self.queue:
            return True

        # Lógica de Bypass para Testes
        if TEST_MODE:
            _LOGGER.info("[TEST MODE] Simulando envio de %s itens para API.", len(self.queue))
            self.queue.clear()
            await self._save_queue_to_disk()
            return True

        # Lógica Real de Produção
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
                    _LOGGER.info("Sincronização bem-sucedida: %s itens enviados.", len(self.queue))
                    self.queue.clear()
                    await self._save_queue_to_disk()
                    return True

                if response.status == 401:
                    _LOGGER.warning("Token expirado. Tentando re-autenticação...")
                    self.token = None
                    return await self.send_queue()

                _LOGGER.warning("API recusou sincronização (Status %s).", response.status)
                return False

        except aiohttp.ClientError as err:
            _LOGGER.warning("Erro de rede na sincronização: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Erro inesperado no cliente API: %s", err)
            return False