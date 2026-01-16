import aiohttp
import asyncio
import logging
import os
import json
import gzip
from datetime import datetime
from typing import List, Dict, Any, Optional

# Importações oficiais do Core para persistência atômica segura
from homeassistant.helpers.json import save_json
from homeassistant.util.json import load_json
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    STORAGE_FILE,
    TEST_MODE,
    MAX_RETRIES,
    RETRY_DELAY,
    HEADERS,
    DEFAULT_PING_HOST
)

_LOGGER = logging.getLogger(__name__)

class EasySmartClient:
    """
    Cliente API exaustivo com persistência nativa HA,
    gestão de concorrência e lógica de re-tentativa (Retry).
    """

    def __init__(self, host: str, username: str, password: str, session: aiohttp.ClientSession, hass: HomeAssistant):
        """Inicializa o cliente com caminhos de armazenamento protegidos pelo Core do HA."""
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.session = session
        self.hass = hass
        self.queue: List[Dict[str, Any]] = []
        self.token: Optional[str] = None

        # Define o caminho absoluto dentro de /config/.storage/
        self.storage_path = hass.config.path(".storage", STORAGE_FILE)

        # Lock de concorrência para evitar que múltiplos envios ocorram simultaneamente
        self._lock = asyncio.Lock()

        # Registro de última comunicação
        self._last_communication_time: Optional[datetime] = None

        _LOGGER.debug("Cliente Easy Smart inicializado. Caminho de armazenamento: %s", self.storage_path)

    async def authenticate(self) -> bool:
        """Realiza a autenticação e obtém o Bearer Token para as requisições."""
        if TEST_MODE:
            _LOGGER.info("MODO TESTE: Simulando sucesso na autenticação.")
            self.token = "token_teste_v10_estavel"
            self._last_communication_time = datetime.now()
            self.hass.add_job(self._save_queue_to_disk)
            return True

        url = f"{self.host}/auth/login"
        payload = {
            "username": self.username,
            "password": self.password
        }

        _LOGGER.debug("Enviando requisição de login para: %s", url)
        try:
            async with self.session.post(url, json=payload, timeout=15) as response:
                if response.status == 200:
                    self._last_communication_time = datetime.now()
                    data = await response.json()
                    self.token = data.get("access_token")
                    _LOGGER.info("Autenticação na API Easy Smart realizada com sucesso.")
                    # Persiste a metadata de sucesso
                    self.hass.add_job(self._save_queue_to_disk)
                    return True

                _LOGGER.error(
                    "Falha na autenticação. Status: %s. Verifique se as credenciais estão corretas.",
                    response.status
                )
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            # Não logamos erro aqui pois o Coordinator tratará a lógica de diagnóstico
            pass
        except Exception as e:
            _LOGGER.error("Erro inesperado no processo de login: %s", e)

        return False

    async def check_internet(self) -> bool:
        """Verifica se há conectividade com a internet básica."""
        try:
            # Tenta uma conexão simples na porta 53 (DNS) ou 80 do host de ping
            # Usando timeout curto para ser rápido
            import socket
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                lambda: socket.create_connection((DEFAULT_PING_HOST, 53), timeout=3)
            )
            return True
        except Exception:
            return False

    def add_to_queue(self, data: Dict[str, Any]):
        """Adiciona dados à fila de telemetria e garante a persistência física imediata."""
        if not isinstance(data, dict):
            _LOGGER.error("Erro de formato: Tentativa de enfileirar dado que não é um dicionário: %s", data)
            return

        # Garante a integridade do timestamp para o histórico da API
        if "timestamp" not in data:
            data["timestamp"] = datetime.now().isoformat()

        self.queue.append(data)
        _LOGGER.debug("Evento de telemetria enfileirado localmente. Itens na fila: %s", len(self.queue))

        # Agenda a gravação para o disco de forma assíncrona (Thread-safe)
        self.hass.add_job(self._save_queue_to_disk)

    async def sync_queue(self) -> bool:
        """
        Sincroniza a fila acumulada com o servidor remoto.
        Implementa Retry, Renovação de Token automático e tratamento de erros de rede.
        """
        if not self.queue:
            # Heartbeat: Se a fila estiver vazia, realizamos uma comunicação mínima
            # apenas para validar a conexão e atualizar o timestamp de "Última Sincronização".
            # Isso garante que o usuário veja que o intervalo está sendo respeitado.
            _LOGGER.debug("Fila vazia. Iniciando heartbeat para manter conexão viva.")
            return await self.authenticate()

        # O Lock garante que se um ciclo de rede demorar, o próximo não atropele o atual
        async with self._lock:
            if TEST_MODE:
                _LOGGER.info("MODO TESTE: Simulação de envio bulk de %s itens concluída.", len(self.queue))
                self._last_communication_time = datetime.now()
                self.queue.clear()
                self._save_queue_to_disk()
                return True

            # Se não temos token, tentamos autenticar antes de prosseguir
            if not self.token and not await self.authenticate():
                _LOGGER.warning("Sincronização cancelada: Falha crítica na autenticação.")
                return False

            attempts = 0
            while attempts < MAX_RETRIES:
                try:
                    url = f"{self.host}/api/telemetria/bulk"
                    auth_headers = {
                        **HEADERS,
                        "Authorization": f"Bearer {self.token}"
                    }

                    _LOGGER.debug("Tentativa de envio bulk %s/%s para %s", attempts + 1, MAX_RETRIES, url)

                    # Comprime os dados com GZIP para reduzir tamanho (70-85% de redução)
                    json_data = json.dumps(self.queue).encode('utf-8')
                    compressed_data = gzip.compress(json_data, compresslevel=6)
                    
                    # Adiciona header indicando que os dados estão comprimidos
                    compressed_headers = {
                        **auth_headers,
                        "Content-Encoding": "gzip",
                        "Content-Type": "application/json"
                    }
                    
                    original_size = len(json_data)
                    compressed_size = len(compressed_data)
                    compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
                    
                    _LOGGER.debug(
                        "Dados comprimidos: %s bytes → %s bytes (%.1f%% reduzido)",
                        original_size, compressed_size, compression_ratio
                    )

                    async with self.session.post(
                        url,
                        data=compressed_data,
                        headers=compressed_headers,
                        timeout=25
                    ) as response:
                        if response.status in [200, 201]:
                            self._last_communication_time = datetime.now()
                            _LOGGER.info("Sucesso! %s eventos de telemetria enviados para a API central.", len(self.queue))
                            self.queue.clear()
                            self._save_queue_to_disk()
                            return True

                        if response.status == 401:
                            _LOGGER.warning("Token expirado (401). Tentando renovação de credenciais...")
                            if await self.authenticate():
                                attempts += 1
                                continue # Tenta o envio novamente com o novo token

                        _LOGGER.warning(
                            "Resposta negativa da API (Status %s). Tentativa %s/%s",
                            response.status, attempts + 1, MAX_RETRIES
                        )

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    _LOGGER.warning(
                        "Falha de rede na comunicação com a API: %s. Aguardando %ss para re-tentativa...",
                        e, RETRY_DELAY
                    )

                attempts += 1
                if attempts < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)

            _LOGGER.error("Falha persistente na sincronização após %s tentativas. Dados mantidos para o próximo ciclo.", MAX_RETRIES)
            return False

    def _save_queue_to_disk(self):
        """
        Gravação robusta da fila e metadata usando helpers oficiais do HA.
        """
        try:
            storage_dir = os.path.dirname(self.storage_path)
            if not os.path.exists(storage_dir):
                os.makedirs(storage_dir, exist_ok=True)

            # Estrutura de dados persistente
            data_to_save = {
                "queue": self.queue,
                "last_communication": self._last_communication_time.isoformat() if self._last_communication_time else None
            }

            # save_json do HA faz a escrita atômica internamente
            save_json(self.storage_path, data_to_save)
            _LOGGER.debug("Estado da fila e metadata persistidos com sucesso.")
        except Exception as e:
            _LOGGER.error("Erro crítico ao salvar dados no disco: %s", e)

    async def load_queue_from_disk(self):
        """Carrega a fila e metadata persistidas durante o boot."""
        if not os.path.exists(self.storage_path):
            return

        try:
            data = await self.hass.async_add_executor_job(load_json, self.storage_path)

            if isinstance(data, dict):
                # Novo formato (v1.3.0+)
                self.queue = data.get("queue", [])
                last_comm_str = data.get("last_communication")
                if last_comm_str:
                    self._last_communication_time = datetime.fromisoformat(last_comm_str)
                _LOGGER.info("Persistência carregada: %s eventos e última comunicação restaurada.", len(self.queue))
            elif isinstance(data, list):
                # Legado (v1.2.0-)
                self.queue = data
                _LOGGER.info("Persistência legada carregada: %s eventos restaurados.", len(self.queue))
            
        except Exception as e:
            _LOGGER.error("Falha ao carregar persistência local: %s", e)
            if os.path.exists(self.storage_path):
                backup_name = f"{self.storage_path}.corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(self.storage_path, backup_name)

    def get_diagnostics(self) -> Dict[str, Any]:
        """Extrai métricas de saúde interna para os sensores de diagnóstico."""
        return {
            "queue_size": len(self.queue),
            "is_authenticated": self.token is not None,
            "api_host": self.host,
            "test_mode": TEST_MODE,
            "storage_location": self.storage_path,
            "last_communication": self._last_communication_time.strftime("%d/%m/%Y %H:%M:%S") if self._last_communication_time else "Aguardando..."
        }